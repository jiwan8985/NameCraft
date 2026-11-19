"""작명 프로젝트·후보·반응 저장 (기획서 §4, §9, §12 일부, REQ-AI-001/002)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from namecraft.db.models import NameCandidate, NameReaction, NamingProject
from namecraft.domain.text import is_hangul_syllable, is_hanja, normalize_name_text
from namecraft.errors import NotFound
from namecraft.services.generation import GenerateRequest
from namecraft.services.ranking import preference_profile

PROJECT_PREF_KEYS = {"syllables", "name_type", "style_tags", "liked_examples", "count", "diversity_threshold",
                     "use_traditional", "weights", "use_saju"}
PROJECT_CONSTRAINT_KEYS = {"include_syllables", "exclude_syllables", "exclude_initials", "exclude_hanja",
                           "fixed_syllable", "fixed_hanja"}


def get_project(session: Session, project_id: str) -> NamingProject:
    p = session.get(NamingProject, project_id)
    if p is None:
        raise NotFound("프로젝트를 찾을 수 없습니다.")
    return p


def project_dict(p: NamingProject) -> dict[str, Any]:
    return {"id": p.id, "title": p.title, "surname_hangul": p.surname_hangul, "surname_hanja": p.surname_hanja,
            "sex": p.sex, "preferences": p.preferences, "constraints": p.constraints,
            "analysis_options": p.analysis_options, "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None}


def create_project(session: Session, data: dict) -> NamingProject:
    surname = normalize_name_text(data["surname_hangul"])
    if not surname or not all(is_hangul_syllable(c) for c in surname):
        raise ValueError("surname_hangul")
    hanja = normalize_name_text(data.get("surname_hanja") or "") or None
    if hanja and (len(hanja) != len(surname) or not all(is_hanja(c) for c in hanja)):
        raise ValueError("surname_hanja")
    p = NamingProject(title=data.get("title") or f"{surname}씨 작명", surname_hangul=surname, surname_hanja=hanja,
                      sex=data.get("sex", "n"),
                      preferences={k: v for k, v in (data.get("preferences") or {}).items() if k in PROJECT_PREF_KEYS},
                      constraints={k: v for k, v in (data.get("constraints") or {}).items()
                                   if k in PROJECT_CONSTRAINT_KEYS},
                      analysis_options=data.get("analysis_options") or {})
    session.add(p)
    session.flush()
    return p


def update_project(session: Session, p: NamingProject, data: dict) -> NamingProject:
    if "title" in data and data["title"]:
        p.title = data["title"]
    if "sex" in data:
        p.sex = data["sex"]
    if "preferences" in data:
        p.preferences = {**p.preferences, **{k: v for k, v in data["preferences"].items() if k in PROJECT_PREF_KEYS}}
    if "constraints" in data:
        p.constraints = {**p.constraints,
                         **{k: v for k, v in data["constraints"].items() if k in PROJECT_CONSTRAINT_KEYS}}
    if "analysis_options" in data:
        p.analysis_options = {**p.analysis_options, **data["analysis_options"]}
    session.flush()
    return p


def candidates(session: Session, project_id: str, *, include_excluded: bool = False) -> list[NameCandidate]:
    q = select(NameCandidate).where(NameCandidate.project_id == project_id)
    if not include_excluded:
        q = q.where(NameCandidate.status != "excluded")
    return list(session.scalars(q.order_by(NameCandidate.created_at, NameCandidate.given_hangul)))


def excluded_names(session: Session, project_id: str) -> list[str]:
    """REQ-AI-002: 제외(싫어요 포함)한 이름은 다시 추천하지 않는다 — 사용자가 해제하면 다시 허용."""
    return sorted({c.given_hangul for c in session.scalars(select(NameCandidate).where(
        NameCandidate.project_id == project_id, NameCandidate.status == "excluded"))})


def generate_request_for(session: Session, p: NamingProject, overrides: dict | None = None) -> GenerateRequest:
    prefs = {**p.preferences, **(overrides or {})}
    liked, _ = liked_disliked(session, p.id)
    existing = [c.given_hangul for c in candidates(session, p.id)]
    return GenerateRequest(
        surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja, sex=p.sex,
        syllables=prefs.get("syllables", 2), name_type=prefs.get("name_type", "hanja"),
        style_tags=prefs.get("style_tags", {}),
        liked_examples=list(dict.fromkeys([*prefs.get("liked_examples", []), *liked])),
        exclude_names=excluded_names(session, p.id) + existing,  # 이미 저장된 후보·제외 이름은 새로 만들지 않음
        count=prefs.get("count", 30), diversity_threshold=prefs.get("diversity_threshold", 0.8),
        use_traditional=prefs.get("use_traditional", True),
        **{k: p.constraints.get(k, {} if k.startswith("fixed") else []) for k in PROJECT_CONSTRAINT_KEYS},
    )


def save_candidates(session: Session, project_id: str, items: list[dict], *, source: str, provider_id: str | None,
                    record_id: str | None) -> list[NameCandidate]:
    saved = []
    for it in items:
        c = NameCandidate(project_id=project_id, given_hangul=it["given_hangul"], given_hanja=it.get("given_hanja") or "",
                          source=it.get("path") or source, provider_id=provider_id, generation_record_id=record_id,
                          ai_reason=it.get("reason"))
        try:
            with session.begin_nested():
                session.add(c)
                session.flush()
            saved.append(c)
        except IntegrityError:  # 같은 이름·한자 중복은 건너뜀
            continue
    return saved


def add_reaction(session: Session, candidate_id: str, reaction: str, reasons: list[str], memo: str | None,
                 member: str = "owner") -> NameReaction:
    c = session.get(NameCandidate, candidate_id)
    if c is None:
        raise NotFound("후보를 찾을 수 없습니다.")
    if reaction not in ("like", "dislike", "hold"):
        raise ValueError("reaction")
    r = NameReaction(candidate_id=c.id, reaction=reaction, reasons=reasons[:10], memo=(memo or None), member=member)
    session.add(r)
    if reaction == "dislike" and member == "owner":
        c.status = "excluded"  # 다시 추천하지 않음 (PATCH 로 해제 가능)
    elif reaction == "like" and c.status == "excluded":
        c.status = "active"
    session.flush()
    return r


def latest_reactions(session: Session, project_id: str, member: str = "owner") -> dict[str, str]:
    rows = session.execute(
        select(NameReaction.candidate_id, NameReaction.reaction, NameReaction.created_at)
        .join(NameCandidate, NameCandidate.id == NameReaction.candidate_id)
        .where(NameCandidate.project_id == project_id, NameReaction.member == member)
        .order_by(NameReaction.created_at)).all()
    out: dict[str, str] = {}
    for cid, reaction, _ in rows:
        out[cid] = reaction
    return out


def liked_disliked(session: Session, project_id: str) -> tuple[list[str], list[str]]:
    latest = latest_reactions(session, project_id)
    by_id = {c.id: c for c in candidates(session, project_id, include_excluded=True)}
    liked = sorted({by_id[i].given_hangul for i, r in latest.items() if r == "like" and i in by_id})
    disliked = sorted({by_id[i].given_hangul for i, r in latest.items() if r == "dislike" and i in by_id})
    return liked, disliked


def profile_for(session: Session, project_id: str) -> dict:
    return preference_profile(*liked_disliked(session, project_id))
