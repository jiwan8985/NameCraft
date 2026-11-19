"""JSON 백업/복원·무결성 검증·완전 삭제 (기획서 §19, REQ-BAK-001, 수용 기준 §23).

- 형식: {"schema": "namecraft.project", "schema_version": 1, "exported_at", "app_version", "checksum_sha256", "data"}
- checksum = sha256(정규화 JSON(data)). 복원 시 불일치하면 거부(변조·손상 감지).
- 복원은 항상 '새 프로젝트'로 만든다(새 ID로 다시 매핑). 기존 데이터를 덮어쓰지 않는다.
- 업로드 원본 파일·추출 텍스트는 개인정보 최소화를 위해 백업에 넣지 않는다(문서 메타만).
- 인증 토큰·AI 명령 경로 등 기기 의존 설정은 포함하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import namecraft
from namecraft.db.models import (
    AIAlertEvent, AIGenerationRecord, AIInvocation, AIQuotaSnapshot, BirthProfile, CrosscheckResult,
    ExtractedAssertion, FamilyMember, FinalNameDecision, ImportedDocument, NameCandidate, NameReaction,
    NamingProject, Report, ScenarioResult, Tournament,
)
from namecraft.errors import AppError
from namecraft.services import imports as im
from namecraft.services import projects as ps

SCHEMA = "namecraft.project"
SCHEMA_VERSION = 1


class BackupError(AppError):
    status_code = 400
    code = "backup_invalid"


def _row(obj) -> dict:
    out = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, datetime) else v
    return out


def canonical(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def export_project(session: Session, project_id: str) -> dict:
    p = ps.get_project(session, project_id)
    q = lambda m, col: [_row(r) for r in session.scalars(select(m).where(col == p.id))]  # noqa: E731
    cands = list(session.scalars(select(NameCandidate).where(NameCandidate.project_id == p.id)))
    cids = [c.id for c in cands]
    rec_ids = {c.generation_record_id for c in cands if c.generation_record_id}
    data = {
        "project": _row(p),
        "candidates": [_row(c) for c in cands],
        "reactions": [_row(r) for r in session.scalars(select(NameReaction).where(NameReaction.candidate_id.in_(cids)))],
        "generation_records": [_row(r) for r in session.scalars(select(AIGenerationRecord).where(
            (AIGenerationRecord.project_id == p.id) | AIGenerationRecord.id.in_(rec_ids)))],
        "birth_profiles": q(BirthProfile, BirthProfile.project_id),
        "scenario_results": q(ScenarioResult, ScenarioResult.project_id),
        "family_members": q(FamilyMember, FamilyMember.project_id),
        "tournaments": q(Tournament, Tournament.project_id),
        "decisions": q(FinalNameDecision, FinalNameDecision.project_id),
        "reports": q(Report, Report.project_id),
        "documents_meta": [{k: v for k, v in _row(d).items() if k in ("original_filename", "kind", "sha256", "size_bytes",
                                                                      "status", "created_at")}
                           for d in session.scalars(select(ImportedDocument).where(
                               ImportedDocument.project_id == p.id, ImportedDocument.status != "deleted"))],
    }
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "exported_at": datetime.now().astimezone().isoformat(),
            "app_version": namecraft.__version__, "checksum_sha256": hashlib.sha256(canonical(data)).hexdigest(),
            "excluded": ["업로드 원본 파일·추출 텍스트", "AI 실행 명령 경로·인증 정보", "AI 사용량 기록"],
            "data": data}


def verify(doc: dict) -> dict:
    problems = []
    if doc.get("schema") != SCHEMA:
        problems.append("schema")
    if doc.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version")
    data = doc.get("data")
    if not isinstance(data, dict) or "project" not in data:
        problems.append("data")
    elif hashlib.sha256(canonical(data)).hexdigest() != doc.get("checksum_sha256"):
        problems.append("checksum")
    return {"ok": not problems, "problems": problems}


def _dt(v):
    return datetime.fromisoformat(v) if isinstance(v, str) else v


def _build(model, row: dict, **override):
    cols = {c.key: c for c in model.__table__.columns}
    kw = {}
    for k, v in {**row, **override}.items():
        if k not in cols:
            continue
        kw[k] = _dt(v) if v is not None and str(cols[k].type).startswith(("DATETIME", "TIMESTAMP")) else v
    return model(**kw)


def import_project(session: Session, doc: dict, *, title_suffix: str = " (복원)") -> NamingProject:
    v = verify(doc)
    if not v["ok"]:
        raise BackupError("백업 파일을 검증하지 못했습니다.", details=v)
    d = doc["data"]
    new = lambda: str(uuid.uuid4())  # noqa: E731
    pid = new()
    ids: dict[str, str] = {}

    def m(old):
        if old is None:
            return None
        ids.setdefault(old, new())
        return ids[old]

    p = _build(NamingProject, d["project"], id=pid, title=(d["project"]["title"] + title_suffix)[:100])
    session.add(p)
    session.flush()
    for r in d["generation_records"]:
        session.add(_build(AIGenerationRecord, r, id=m(r["id"]), project_id=pid))
    session.flush()
    for c in d["candidates"]:
        session.add(_build(NameCandidate, c, id=m(c["id"]), project_id=pid,
                           generation_record_id=m(c["generation_record_id"]) if c.get("generation_record_id") else None))
    session.flush()
    for fm in d["family_members"]:
        session.add(_build(FamilyMember, fm, id=m(fm["id"]), project_id=pid))
    session.flush()
    for r in d["reactions"]:
        member = r["member"]
        if member.startswith("member:"):
            member = "member:" + m(member.split(":", 1)[1])
        session.add(_build(NameReaction, r, id=new(), candidate_id=m(r["candidate_id"]), member=member))
    for b in d["birth_profiles"]:
        session.add(_build(BirthProfile, b, id=m(b["id"]), project_id=pid))
    session.flush()
    for s in d["scenario_results"]:
        session.add(_build(ScenarioResult, s, id=new(), project_id=pid, birth_profile_id=m(s["birth_profile_id"])))
    for t in d["tournaments"]:
        rounds = [[{**x, "a": m(x["a"]), "b": m(x["b"]) if x.get("b") else None} for x in rnd] for rnd in t["rounds"]]
        res = dict(t.get("result") or {})
        if res:
            res["winner"] = m(res["winner"]) if res.get("winner") else None
            res["finalists"] = [m(x) for x in res.get("finalists", [])]
        session.add(_build(Tournament, t, id=new(), project_id=pid, rounds=rounds, result=res))
    for fd in d["decisions"]:
        session.add(_build(FinalNameDecision, fd, id=new(), project_id=pid, finalists=[m(x) for x in fd["finalists"]],
                           chosen_candidate_id=m(fd["chosen_candidate_id"]) if fd.get("chosen_candidate_id") else None,
                           birth_profile_id=m(fd["birth_profile_id"]) if fd.get("birth_profile_id") else None))
    for rp in d["reports"]:
        session.add(_build(Report, rp, id=new(), project_id=pid))
    session.flush()
    return p


# ---------------------------------------------------------------- 삭제

def delete_project(session: Session, var_dir: Path, project_id: str) -> dict:
    p = ps.get_project(session, project_id)
    docs = list(session.scalars(select(ImportedDocument).where(ImportedDocument.project_id == p.id)))
    for doc in docs:
        try:
            im.file_path(var_dir, doc).unlink(missing_ok=True)
        except Exception:
            pass
        session.execute(delete(ExtractedAssertion).where(ExtractedAssertion.document_id == doc.id))
        session.execute(delete(CrosscheckResult).where(CrosscheckResult.document_id == doc.id))
        session.delete(doc)
    cids = list(session.scalars(select(NameCandidate.id).where(NameCandidate.project_id == p.id)))
    session.execute(delete(NameReaction).where(NameReaction.candidate_id.in_(cids)))
    for model in (ScenarioResult, Report, Tournament, FinalNameDecision, FamilyMember):
        session.execute(delete(model).where(model.project_id == p.id))
    session.execute(delete(NameCandidate).where(NameCandidate.project_id == p.id))
    session.execute(delete(BirthProfile).where(BirthProfile.project_id == p.id))
    session.execute(delete(AIGenerationRecord).where(AIGenerationRecord.project_id == p.id))
    session.execute(delete(AIInvocation).where(AIInvocation.project_id == p.id))
    session.delete(p)
    session.flush()
    return {"project_id": project_id, "deleted_documents": len(docs), "deleted_candidates": len(cids)}


def delete_all_user_data(session: Session, var_dir: Path) -> dict:
    """참조 데이터(한자·성씨·출처)는 남기고 사용자 데이터만 삭제."""
    n = 0
    for pid in list(session.scalars(select(NamingProject.id))):
        delete_project(session, var_dir, pid)
        n += 1
    for doc in session.scalars(select(ImportedDocument)):
        try:
            im.file_path(var_dir, doc).unlink(missing_ok=True)
        except Exception:
            pass
    for model in (ExtractedAssertion, CrosscheckResult, ImportedDocument, AIInvocation, AIQuotaSnapshot, AIAlertEvent,
                  AIGenerationRecord):
        session.execute(delete(model))
    session.flush()
    return {"deleted_projects": n}
