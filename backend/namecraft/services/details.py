"""후보 상세 데이터 (API /candidates/{id} 와 보고서가 같이 사용)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import AIGenerationRecord, NameCandidate, NameReaction
from namecraft.domain.numerology.core import NumerologyOptions
from namecraft.errors import NotFound
from namecraft.services import projects as ps
from namecraft.services.ai_generation import template_explanation
from namecraft.services.name_analysis import analyze_full
from namecraft.services.ranking import rank_names

OPTION_KEYS = ("stroke_system", "single_name_virtual_stroke", "eumryeong_school", "numeral_by_meaning")


def cand_dict(c: NameCandidate) -> dict:
    return {"id": c.id, "given_hangul": c.given_hangul, "given_hanja": c.given_hanja or None, "source": c.source,
            "status": c.status, "provider_id": c.provider_id, "ai_reason": c.ai_reason}


def scenario_list(session: Session, project_id: str) -> list[dict] | None:
    from namecraft.services.collab import latest_snapshot

    snap = latest_snapshot(session, project_id)
    return snap.summary["scenarios"] if snap else None


def numerology_options(p) -> NumerologyOptions:
    return NumerologyOptions(**{k: v for k, v in (p.analysis_options or {}).items() if k in OPTION_KEYS})


def candidate_detail_data(session: Session, candidate_id: str) -> dict[str, Any]:
    c = session.get(NameCandidate, candidate_id)
    if c is None:
        raise NotFound("후보를 찾을 수 없습니다.")
    p = ps.get_project(session, c.project_id)
    opts = numerology_options(p)
    analysis = analyze_full(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                            given_hangul=c.given_hangul, given_hanja=c.given_hanja or None, numerology_options=opts)
    ranked = rank_names(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja, names=[cand_dict(c)],
                        weights=p.preferences.get("weights"), profile=ps.profile_for(session, p.id),
                        use_saju=bool(p.preferences.get("use_saju")), numerology_options=opts,
                        saju_scenarios=scenario_list(session, p.id))["items"][0]
    reactions = [{"reaction": r.reaction, "reasons": r.reasons, "memo": r.memo, "member": r.member,
                  "created_at": r.created_at.isoformat()}
                 for r in session.scalars(select(NameReaction).where(NameReaction.candidate_id == c.id)
                                          .order_by(NameReaction.created_at))]
    rec = session.get(AIGenerationRecord, c.generation_record_id) if c.generation_record_id else None
    generation = None if rec is None else {
        "provider_id": rec.provider_id, "model_id": rec.model_id, "execution_mode": rec.execution_mode,
        "prompt_version": rec.prompt_version, "seed": rec.seed, "status": rec.status,
        "fallback_reason": rec.fallback_reason, "created_at": rec.created_at.isoformat()}
    return {"candidate": cand_dict(c), "project": ps.project_dict(p), "analysis": analysis, "ranking": ranked,
            "reactions": reactions, "generation": generation, "explanation": template_explanation(analysis)}
