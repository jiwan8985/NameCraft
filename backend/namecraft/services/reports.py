"""보고서 (기획서 §19, REQ-RPT-001).

PDF 는 인쇄용 화면 + 브라우저 'PDF로 저장'으로 만든다(D-043). 서버는 보고서 데이터 스냅샷을 만들고 보관해
같은 보고서를 다시 열 수 있게 한다(재생성 시 당시 데이터 그대로).
모든 보고서에: 입력 조건, 출생정보 예정/확정 구분, 적용 학파·옵션, 공식 한자 확인일, 계산 버전, 해석 한계.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import namecraft
from namecraft.db.models import DataReleaseVersion, NameCandidate, Report
from namecraft.domain.calendar import ENGINE_VERSION
from namecraft.domain.numerology.core import RULE_VERSION
from namecraft.errors import AppError
from namecraft.services import collab as cb
from namecraft.services import finalize as fz
from namecraft.services import projects as ps
from namecraft.services.details import cand_dict, candidate_detail_data, numerology_options, scenario_list
from namecraft.services.ranking import RANKING_VERSION, rank_names, sort_items

LIMITATIONS = [
    "사주·수리·오행·81수리 길흉은 전통 해석이며 과학적 근거가 없습니다. 이름이 건강·성공·운명을 결정하지 않습니다.",
    "81수리 분류는 통용 분류를 정리한 것으로 특정 문헌과 대조하지 않았습니다(출처 대조 전).",
    "한자 독음·획수 기초 자료는 Unicode Unihan(비공식)이며, 인명용 한자 허용 여부는 공식 조회로 확인해야 합니다.",
    "만세력 계산은 천문 계산 기반이며 한국천문연구원 기준값과의 최종 대조가 남아 있을 수 있습니다.",
    "부정 연상·뜻 주의는 소규모 목록 대조 결과(후보)이며 판정이 아닙니다.",
    "이 보고서는 출생신고를 대신하거나 신고 수리를 보장하지 않습니다.",
]
KINDS = ("project_summary", "name_detail", "comparison")


class ReportError(AppError):
    status_code = 400
    code = "report_invalid"


def _versions(session: Session) -> dict:
    return {"app": namecraft.__version__, "ranking": RANKING_VERSION, "numerology_rule": RULE_VERSION,
            "calendar_engine": ENGINE_VERSION,
            "data_releases": [r.id for r in session.scalars(select(DataReleaseVersion).order_by(DataReleaseVersion.id))]}


def _conditions(session: Session, p) -> dict:
    b = cb.current_profile(session, p.id)
    return {"project": ps.project_dict(p),
            "birth": None if b is None else {**cb.profile_dict(b), "kind_label": "확정" if b.kind == "actual" else "예정"},
            "school_options": {**numerology_options(p).__dict__, "use_saju": bool(p.preferences.get("use_saju")),
                               "saju_interpretation": "saju.complement.simple.v0" if p.preferences.get("use_saju") else None,
                               "true_solar_time": b.true_solar_time if b else None,
                               "zi_convention": b.zi_convention if b else None}}


def build(session: Session, project_id: str, kind: str, candidate_ids: list[str] | None = None) -> Report:
    if kind not in KINDS:
        raise ReportError(f"보고서 종류: {KINDS}")
    p = ps.get_project(session, project_id)
    snap: dict[str, Any] = {"kind": kind, "conditions": _conditions(session, p), "limitations": LIMITATIONS,
                            "generated_at": datetime.now(UTC).isoformat()}
    official_basis = fz.check(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                              given_hangul="가", given_hanja=None)["data_basis"]
    snap["official_basis"] = official_basis

    if kind == "project_summary":
        cands = ps.candidates(session, p.id)
        ranked = rank_names(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                            names=[cand_dict(c) for c in cands], weights=p.preferences.get("weights"),
                            profile=ps.profile_for(session, p.id), use_saju=bool(p.preferences.get("use_saju")),
                            numerology_options=numerology_options(p), saju_scenarios=scenario_list(session, p.id))
        snap["ranking"] = {"weights_normalized": ranked["weights_normalized"],
                           "items": sort_items(ranked["items"], "overall")[:30]}
        latest = cb.latest_snapshot(session, p.id)
        snap["scenario"] = None if latest is None else {k: latest.summary[k] for k in (
            "base_solar_date", "dates", "scenario_count", "distinct_charts", "varying_pillars", "element_ranges", "notes")}
        board = cb.current_board(session, p.id)
        if board and board.chosen_candidate_id:
            c = session.get(NameCandidate, board.chosen_candidate_id)
            snap["decision"] = {"name": p.surname_hangul + c.given_hangul, "hanja": c.given_hanja or None,
                                "reason": board.reason, "decided_at": board.created_at.isoformat()}
            snap["finalize_check"] = fz.check(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                                              given_hangul=c.given_hangul, given_hanja=c.given_hanja or None)
        snap["family"] = cb.family_summary(session, p.id)
    elif kind == "name_detail":
        if not candidate_ids or len(candidate_ids) != 1:
            raise ReportError("이름 상세 보고서는 후보 1개가 필요합니다.")
        _own(session, p.id, candidate_ids)
        snap["detail"] = candidate_detail_data(session, candidate_ids[0])
    else:
        if not candidate_ids or not 2 <= len(candidate_ids) <= 10:
            raise ReportError("비교 보고서는 후보 2~10개가 필요합니다.")
        cands = _own(session, p.id, candidate_ids)
        ranked = rank_names(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                            names=[cand_dict(c) for c in cands], weights=p.preferences.get("weights"),
                            profile=ps.profile_for(session, p.id), use_saju=bool(p.preferences.get("use_saju")),
                            numerology_options=numerology_options(p), saju_scenarios=scenario_list(session, p.id))
        snap["comparison"] = ranked
    r = Report(project_id=p.id, kind=kind, params={"candidate_ids": candidate_ids or []}, snapshot=snap,
               versions=_versions(session))
    session.add(r)
    session.flush()
    return r


def _own(session: Session, project_id: str, ids: list[str]) -> list[NameCandidate]:
    cands = [session.get(NameCandidate, i) for i in ids]
    if any(c is None or c.project_id != project_id for c in cands):
        raise ReportError("이 프로젝트의 후보만 넣을 수 있습니다.")
    return cands  # type: ignore[return-value]


CSV_HEADER = ["순위", "이름", "한자", "종합", "발음", "의미", "사주", "수리", "사용성", "선호", "공식한자", "검토", "출처", "반응",
              "N/A 항목"]


def candidates_csv(session: Session, project_id: str) -> str:
    p = ps.get_project(session, project_id)
    cands = ps.candidates(session, p.id)
    ranked = rank_names(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                        names=[cand_dict(c) for c in cands], weights=p.preferences.get("weights"),
                        profile=ps.profile_for(session, p.id), use_saju=bool(p.preferences.get("use_saju")),
                        numerology_options=numerology_options(p), saju_scenarios=scenario_list(session, p.id))
    latest = ps.latest_reactions(session, p.id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADER)
    na = lambda v: "N/A" if v is None else v  # noqa: E731
    for i, it in enumerate(sort_items(ranked["items"], "overall"), 1):
        c = it["categories"]
        w.writerow([i, it["full_hangul"], it["given_hanja"] or "", na(it["overall"]),
                    *[na(c[k]["score"]) for k in ("phonetic", "meaning", "saju", "numerology", "usability", "preference")],
                    it["gate"]["official_hanja"] if it["given_hanja"] else "hangul_name", it["gate"]["caution"],
                    it.get("source") or "", latest.get(it["id"], ""), " ".join(it["incomplete"])])
    return "﻿" + buf.getvalue()  # Excel 한글 깨짐 방지(BOM)
