"""보고서·내보내기·백업/복원·완전 삭제 (기획서 §18 POST /reports, §19)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import NamingProject, Report
from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import backup as bk
from namecraft.services import projects as ps
from namecraft.services import reports as rp
from namecraft_api.deps import get_db

router = APIRouter(tags=["reports", "backup"])


class ReportIn(BaseModel):
    project_id: str
    kind: Literal["project_summary", "name_detail", "comparison"]
    candidate_ids: list[str] | None = Field(default=None, max_length=10)


@router.post("/reports", response_model=Envelope[dict[str, Any]], status_code=201)
def create_report(body: ReportIn, db: Session = Depends(get_db)):
    r = rp.build(db, body.project_id, body.kind, body.candidate_ids)
    db.commit()
    return envelope(_report(r), verification_status=VerificationStatus.calculated,
                    warnings=[{"code": "print_to_pdf", "message": "PDF 는 보고서 화면에서 인쇄 → 'PDF로 저장'으로 만듭니다."}])


def _report(r: Report) -> dict:
    return {"id": r.id, "project_id": r.project_id, "kind": r.kind, "params": r.params, "versions": r.versions,
            "created_at": r.created_at.isoformat(), "snapshot": r.snapshot}


@router.get("/reports/{report_id}", response_model=Envelope[dict[str, Any]])
def get_report(report_id: str, db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r is None:
        raise NotFound("보고서를 찾을 수 없습니다.")
    return envelope(_report(r), warnings=[{"code": "snapshot", "message": "생성 당시 데이터로 다시 보여줍니다."}])


@router.get("/projects/{project_id}/reports", response_model=Envelope[list[dict[str, Any]]])
def list_reports(project_id: str, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    rows = db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc()))
    return envelope([{k: v for k, v in _report(r).items() if k != "snapshot"} for r in rows])


@router.get("/projects/{project_id}/candidates.csv")
def candidates_csv(project_id: str, db: Session = Depends(get_db)):
    text = rp.candidates_csv(db, project_id)
    return Response(text.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="candidates.csv"'})


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, db: Session = Depends(get_db)):
    import json

    doc = bk.export_project(db, project_id)
    return Response(json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8"), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="namecraft-project.json"'})


@router.post("/backup/verify", response_model=Envelope[dict[str, Any]])
def verify_backup(doc: dict, db: Session = Depends(get_db)):
    return envelope(bk.verify(doc))


@router.post("/projects/import", response_model=Envelope[dict[str, Any]], status_code=201)
def import_project(doc: dict, db: Session = Depends(get_db)):
    p = bk.import_project(db, doc)
    db.commit()
    return envelope(ps.project_dict(p), warnings=[{"code": "restored_as_new",
                                                   "message": "새 프로젝트로 복원했습니다. 기존 데이터는 바뀌지 않습니다."}])


@router.get("/backup")
def full_backup(db: Session = Depends(get_db)):
    import json

    docs = [bk.export_project(db, pid) for pid in db.scalars(select(NamingProject.id))]
    body = {"schema": "namecraft.backup", "schema_version": 1, "projects": docs}
    return Response(json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8"), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="namecraft-backup.json"'})


@router.post("/backup/restore", response_model=Envelope[dict[str, Any]], status_code=201)
def restore_backup(body: dict, db: Session = Depends(get_db)):
    if body.get("schema") != "namecraft.backup" or not isinstance(body.get("projects"), list):
        raise AppError("전체 백업 파일 형식이 아닙니다.")
    checks = [bk.verify(d) for d in body["projects"]]
    if not all(c["ok"] for c in checks):
        raise AppError("백업 검증에 실패한 프로젝트가 있습니다. 아무것도 복원하지 않았습니다.", details={"checks": checks})
    restored = [bk.import_project(db, d).id for d in body["projects"]]
    db.commit()
    return envelope({"restored_projects": restored})


@router.delete("/projects/{project_id}", response_model=Envelope[dict[str, Any]])
def delete_project(project_id: str, request: Request, db: Session = Depends(get_db)):
    res = bk.delete_project(db, request.app.state.settings.var_dir, project_id)
    db.commit()
    return envelope(res)


class WipeIn(BaseModel):
    confirm: str


@router.post("/data/delete-all", response_model=Envelope[dict[str, Any]])
def delete_all(body: WipeIn, request: Request, db: Session = Depends(get_db)):
    if body.confirm != "DELETE ALL":
        raise AppError("확인 문구 'DELETE ALL' 이 필요합니다.")
    res = bk.delete_all_user_data(db, request.app.state.settings.var_dir)
    db.commit()
    return envelope(res, warnings=[{"code": "reference_data_kept",
                                    "message": "한자·성씨·출처 등 참조 데이터는 남기고 사용자 데이터만 삭제했습니다."}])
