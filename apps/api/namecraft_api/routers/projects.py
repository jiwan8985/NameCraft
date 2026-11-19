"""프로젝트·후보·반응 API (기획서 §18: POST/PATCH /projects, POST /reactions) + 후보 생성·랭킹."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import NameCandidate, NamingProject
from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import ai_generation as aig
from namecraft.services import projects as ps
from namecraft.services.ranking import RankingError, rank_names, sort_items
from namecraft_api.deps import get_db

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    sex: Literal["m", "f", "n"] = "n"
    preferences: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    analysis_options: dict[str, Any] = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    sex: Literal["m", "f", "n"] | None = None
    preferences: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None
    analysis_options: dict[str, Any] | None = None


@router.post("/projects", response_model=Envelope[dict[str, Any]], status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(get_db)):
    try:
        p = ps.create_project(db, body.model_dump())
    except ValueError as e:
        raise AppError("성씨 표기가 올바르지 않습니다.", details={"field": str(e)}) from None
    db.commit()
    return envelope(ps.project_dict(p))


@router.get("/projects", response_model=Envelope[list[dict[str, Any]]])
def list_projects(db: Session = Depends(get_db)):
    rows = db.scalars(select(NamingProject).order_by(NamingProject.created_at.desc()))
    return envelope([ps.project_dict(p) for p in rows])


@router.get("/projects/{project_id}", response_model=Envelope[dict[str, Any]])
def get_project(project_id: str, db: Session = Depends(get_db)):
    return envelope(ps.project_dict(ps.get_project(db, project_id)))


@router.patch("/projects/{project_id}", response_model=Envelope[dict[str, Any]])
def patch_project(project_id: str, body: ProjectPatch, db: Session = Depends(get_db)):
    p = ps.update_project(db, ps.get_project(db, project_id), body.model_dump(exclude_none=True))
    db.commit()
    return envelope(ps.project_dict(p))


class CandidateGenerateIn(BaseModel):
    provider: Literal["auto", "ollama", "claude_code", "antigravity", "none"] = "none"
    count: int | None = Field(default=None, ge=1, le=60)
    send_fields: list[str] | None = None
    consent: bool = False
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


@router.post("/projects/{project_id}/candidates/generate", response_model=Envelope[dict[str, Any]])
def generate_candidates(project_id: str, body: CandidateGenerateIn, request: Request, db: Session = Depends(get_db)):
    p = ps.get_project(db, project_id)
    req = ps.generate_request_for(db, p, {"count": body.count} if body.count else None)
    try:
        res = aig.run_ai_generation(db, req, provider=body.provider, send_fields=body.send_fields,
                                    consent=body.consent, seed=body.seed, project_id=p.id,
                                    ollama_url=request.app.state.settings.ollama_url)
    except aig.AIConsentRequired as e:
        raise AppError("외부 AI 로 보내기 전에 전송 내용 확인과 동의가 필요합니다.",
                       details={"consent_required": True, "preview": e.preview}) from None
    except ValueError as e:
        raise AppError(str(e)) from None
    saved = ps.save_candidates(db, p.id, res.candidates, source="ai_based" if res.provider_used != "rule_based"
                               else "rule_based", provider_id=res.provider_used, record_id=res.record_id)
    db.commit()
    warnings = []
    if res.fallback_reason:
        warnings.append({"code": "ai_fallback", "message": "AI 경로를 사용할 수 없어 규칙 기반 엔진으로 생성했습니다."})
    return envelope({"provider_used": res.provider_used, "execution_mode": res.mode, "record_id": res.record_id,
                     "fallback_reason": res.fallback_reason, "attempts": res.attempts,
                     "saved": [_cand(c) for c in saved], "validation": res.validation},
                    warnings=warnings, verification_status=VerificationStatus.calculated)


def _scenarios(db: Session, project_id: str) -> list[dict] | None:
    from namecraft.services.collab import latest_snapshot

    snap = latest_snapshot(db, project_id)
    return snap.summary["scenarios"] if snap else None


def _cand(c: NameCandidate) -> dict:
    return {"id": c.id, "given_hangul": c.given_hangul, "given_hanja": c.given_hanja or None, "source": c.source,
            "status": c.status, "provider_id": c.provider_id, "ai_reason": c.ai_reason}


class CandidateIn(BaseModel):
    given_hangul: str = Field(min_length=1, max_length=6)
    given_hanja: str | None = Field(default=None, max_length=6)


@router.post("/projects/{project_id}/candidates", response_model=Envelope[dict[str, Any]], status_code=201)
def add_candidate(project_id: str, body: CandidateIn, db: Session = Depends(get_db)):
    from namecraft.domain.text import is_hangul_syllable, is_hanja, normalize_name_text

    p = ps.get_project(db, project_id)
    g = normalize_name_text(body.given_hangul)
    h = normalize_name_text(body.given_hanja) if body.given_hanja else None
    if not all(is_hangul_syllable(c) for c in g) or (h and (len(h) != len(g) or not all(is_hanja(c) for c in h))):
        raise AppError("이름 표기가 올바르지 않습니다.")
    saved = ps.save_candidates(db, p.id, [{"given_hangul": g, "given_hanja": h}], source="user", provider_id=None,
                               record_id=None)
    if not saved:
        raise AppError("이미 있는 후보입니다.", details={"duplicate": True})
    db.commit()
    return envelope(_cand(saved[0]))


@router.get("/projects/{project_id}/candidates", response_model=Envelope[dict[str, Any]])
def list_candidates(project_id: str, sort: str = Query("overall"), include_excluded: bool = False,
                    db: Session = Depends(get_db)):
    p = ps.get_project(db, project_id)
    cands = ps.candidates(db, p.id, include_excluded=include_excluded)
    latest = ps.latest_reactions(db, p.id)
    try:
        ranked = rank_names(db, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                            names=[_cand(c) for c in cands], weights=p.preferences.get("weights"),
                            profile=ps.profile_for(db, p.id), use_saju=bool(p.preferences.get("use_saju")),
                            saju_scenarios=_scenarios(db, p.id))
        items = sort_items(ranked["items"], sort)
    except RankingError as e:
        raise AppError(str(e)) from None
    for it in items:
        it["reaction"] = latest.get(it["id"])
    warnings = []
    if any(it["incomplete"] for it in items):
        warnings.append({"code": "incomplete_data",
                         "message": "근거 자료가 없는 항목은 N/A 로 두고 나머지 항목 비중을 다시 계산했습니다."})
    if any(it["gate"]["official_hanja"] == "unknown" for it in items):
        warnings.append({"code": "official_gate_unknown",
                         "message": "공식 인명용 한자 확인 전인 후보가 있습니다(점수와 별개로 표시)."})
    return envelope({"project_id": p.id, "sort": sort, "ranking_version": ranked["ranking_version"],
                     "weights_normalized": ranked["weights_normalized"], "items": items},
                    warnings=warnings, verification_status=VerificationStatus.calculated,
                    calculation_assumptions=["종합 = 사용 가능한 항목의 가중 평균(합 100%로 재정규화)",
                                             "유효성(공식 한자)은 점수에 섞지 않고 gate 로 표시",
                                             "전통 해석 항목은 학파 프로필 내 상대 평가"])


class CandidatePatch(BaseModel):
    status: Literal["active", "excluded", "favorite"]


@router.patch("/candidates/{candidate_id}", response_model=Envelope[dict[str, Any]])
def patch_candidate(candidate_id: str, body: CandidatePatch, db: Session = Depends(get_db)):
    c = db.get(NameCandidate, candidate_id)
    if c is None:
        raise NotFound("후보를 찾을 수 없습니다.")
    c.status = body.status  # excluded → active 로 '다시 추천 허용' (REQ-AI-002)
    db.commit()
    return envelope(_cand(c))


class ReactionIn(BaseModel):
    candidate_id: str
    reaction: Literal["like", "dislike", "hold"]
    reasons: list[str] = Field(default_factory=list, max_length=10)
    memo: str | None = Field(default=None, max_length=1000)


@router.post("/reactions", response_model=Envelope[dict[str, Any]], status_code=201)
def post_reaction(body: ReactionIn, db: Session = Depends(get_db)):
    r = ps.add_reaction(db, body.candidate_id, body.reaction, body.reasons, body.memo)
    db.commit()
    c = db.get(NameCandidate, body.candidate_id)
    return envelope({"id": r.id, "candidate": _cand(c), "reaction": r.reaction})


@router.get("/candidates/{candidate_id}", response_model=Envelope[dict[str, Any]])
def candidate_detail(candidate_id: str, db: Session = Depends(get_db)):
    """이름 상세(/names/:id): 전체 분석 + 랭킹 항목별 근거 + 반응 이력 + 생성 기록."""
    from namecraft.db.models import AIGenerationRecord, NameReaction
    from namecraft.domain.numerology.core import NumerologyOptions
    from namecraft.services.name_analysis import analyze_full

    c = db.get(NameCandidate, candidate_id)
    if c is None:
        raise NotFound("후보를 찾을 수 없습니다.")
    p = ps.get_project(db, c.project_id)
    opts = NumerologyOptions(**{k: v for k, v in (p.analysis_options or {}).items()
                                if k in ("stroke_system", "single_name_virtual_stroke", "eumryeong_school",
                                         "numeral_by_meaning")})
    analysis = analyze_full(db, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                            given_hangul=c.given_hangul, given_hanja=c.given_hanja or None, numerology_options=opts)
    ranked = rank_names(db, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja, names=[_cand(c)],
                        weights=p.preferences.get("weights"), profile=ps.profile_for(db, p.id),
                        use_saju=bool(p.preferences.get("use_saju")), numerology_options=opts,
                        saju_scenarios=_scenarios(db, p.id))["items"][0]
    reactions = [{"reaction": r.reaction, "reasons": r.reasons, "memo": r.memo, "member": r.member,
                  "created_at": r.created_at.isoformat()}
                 for r in db.scalars(select(NameReaction).where(NameReaction.candidate_id == c.id)
                                     .order_by(NameReaction.created_at))]
    rec = db.get(AIGenerationRecord, c.generation_record_id) if c.generation_record_id else None
    generation = None if rec is None else {
        "provider_id": rec.provider_id, "model_id": rec.model_id, "execution_mode": rec.execution_mode,
        "prompt_version": rec.prompt_version, "seed": rec.seed, "status": rec.status,
        "fallback_reason": rec.fallback_reason, "created_at": rec.created_at.isoformat()}
    from namecraft.services.ai_generation import template_explanation

    return envelope({"candidate": _cand(c), "project": ps.project_dict(p), "analysis": analysis, "ranking": ranked,
                     "reactions": reactions, "generation": generation,
                     "explanation": template_explanation(analysis)},
                    verification_status=VerificationStatus.calculated)
