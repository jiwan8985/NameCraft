"""작명소 자료 가져오기·교차검증 API (기획서 §18: POST /imports, /imports/{id}/crosscheck) + 출생신고 점검."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import CrosscheckResult, ImportedDocument, NameCandidate
from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import collab as cb
from namecraft.services import crosscheck as cx
from namecraft.services import finalize as fz
from namecraft.services import imports as im
from namecraft.services import projects as ps
from namecraft_api.deps import get_db

router = APIRouter(tags=["imports", "finalize"])

WARNING_TEXT = {
    "ocr_unavailable": "이미지 글자 인식(OCR) 도구가 없어 자동 추출하지 않았습니다. 원본을 보며 값을 직접 입력하세요.",
    "pdf_no_text_layer": "PDF 에 글자 정보가 없습니다(스캔본). 원본을 보며 값을 직접 입력하세요.",
    "pdf_read_error": "PDF 를 읽지 못했습니다.",
    "instruction_like_text": "문서에 지시문처럼 보이는 문장이 있습니다. 문서 내용은 데이터로만 쓰이며 명령으로 실행되지 않습니다.",
}


def _w(doc) -> list[dict]:
    out = [{"code": c, "message": WARNING_TEXT.get(c, c)} for c in doc.warnings]
    out.append({"code": "review_required", "message": "추출값은 자동 인식 결과입니다. 원문과 비교해 확인·수정한 값만 교차검증에 쓰입니다."})
    return out


@router.post("/imports", response_model=Envelope[dict[str, Any]], status_code=201)
async def upload(request: Request, file: UploadFile = File(...), project_id: str | None = Form(default=None),
                 db: Session = Depends(get_db)):
    if project_id:
        ps.get_project(db, project_id)
    data = await file.read(im.MAX_BYTES + 1)
    doc = im.store_upload(db, request.app.state.settings.var_dir, filename=file.filename or "upload", data=data,
                          project_id=project_id)
    db.commit()
    return envelope(im.doc_dict(doc, im.assertions_of(db, doc.id)), warnings=_w(doc),
                    verification_status=VerificationStatus.unverified)


@router.get("/imports", response_model=Envelope[list[dict[str, Any]]])
def list_imports(project_id: str | None = None, db: Session = Depends(get_db)):
    q = select(ImportedDocument).where(ImportedDocument.status != "deleted")
    if project_id:
        q = q.where(ImportedDocument.project_id == project_id)
    rows = db.scalars(q.order_by(ImportedDocument.created_at.desc()))
    return envelope([{k: v for k, v in im.doc_dict(d, []).items() if k not in ("extracted_text", "assertions")}
                     for d in rows])


@router.get("/imports/{doc_id}", response_model=Envelope[dict[str, Any]])
def get_import(doc_id: str, db: Session = Depends(get_db)):
    doc = im.get_doc(db, doc_id)
    latest = db.scalars(select(CrosscheckResult).where(CrosscheckResult.document_id == doc.id)
                        .order_by(CrosscheckResult.created_at.desc())).first()
    data = im.doc_dict(doc, im.assertions_of(db, doc.id))
    data["crosscheck"] = {"id": latest.id, "summary": latest.summary, "items": latest.items,
                          "created_at": latest.created_at.isoformat()} if latest else None
    return envelope(data, warnings=_w(doc), verification_status=VerificationStatus.unverified)


@router.get("/imports/{doc_id}/file")
def get_import_file(doc_id: str, request: Request, db: Session = Depends(get_db)):
    doc = im.get_doc(db, doc_id)
    p = im.file_path(request.app.state.settings.var_dir, doc)
    if not p.exists():
        raise NotFound("파일 없음")
    return FileResponse(p, media_type=doc.media_type, headers={
        "Content-Disposition": "inline", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"})


class ManualIn(BaseModel):
    field: str = Field(max_length=40)
    value: str = Field(min_length=1, max_length=200)


@router.post("/imports/{doc_id}/assertions", response_model=Envelope[dict[str, Any]], status_code=201)
def add_assertion(doc_id: str, body: ManualIn, db: Session = Depends(get_db)):
    a = im.add_manual(db, doc_id, body.field, body.value)
    db.commit()
    return envelope({"id": a.id, "field": a.field, "value": a.value, "review_status": a.review_status})


class ReviewIn(BaseModel):
    review_status: Literal["accepted", "corrected", "rejected"]
    corrected_value: str | None = Field(default=None, max_length=200)


@router.patch("/assertions/{assertion_id}", response_model=Envelope[dict[str, Any]])
def review_assertion(assertion_id: str, body: ReviewIn, db: Session = Depends(get_db)):
    a = im.review(db, assertion_id, body.review_status, body.corrected_value)
    db.commit()
    return envelope({"id": a.id, "review_status": a.review_status, "corrected_value": a.corrected_value})


@router.post("/imports/{doc_id}/crosscheck", response_model=Envelope[dict[str, Any]])
def crosscheck(doc_id: str, db: Session = Depends(get_db)):
    doc = im.get_doc(db, doc_id)
    project = ps.get_project(db, doc.project_id) if doc.project_id else None
    bp = cb.current_profile(db, doc.project_id) if doc.project_id else None
    r = cx.run_crosscheck(db, doc_id, project=project, birth_profile=bp)
    db.commit()
    pending = sum(1 for a in im.assertions_of(db, doc.id) if a.review_status == "pending")
    warnings = [{"code": "reproducibility_only", "message": r.summary["note"]}]
    if pending:
        warnings.append({"code": "unreviewed_excluded", "message": f"검토하지 않은 추출값 {pending}개는 비교에서 제외했습니다."})
    return envelope({"id": r.id, "summary": r.summary, "items": r.items, "engine_versions": r.engine_versions},
                    warnings=warnings, verification_status=VerificationStatus.calculated)


@router.delete("/imports/{doc_id}", response_model=Envelope[dict[str, Any]])
def delete_import(doc_id: str, request: Request, db: Session = Depends(get_db)):
    im.delete_doc(db, request.app.state.settings.var_dir, doc_id)
    db.commit()
    return envelope({"id": doc_id, "deleted": True})


# ---------------------------------------------------------------- 출생신고 준비

class FinalizeIn(BaseModel):
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    given_hangul: str = Field(min_length=1, max_length=10)
    given_hanja: str | None = Field(default=None, max_length=10)


@router.post("/finalize/check", response_model=Envelope[dict[str, Any]])
def finalize_check(body: FinalizeIn, db: Session = Depends(get_db)):
    data = fz.check(db, surname_hangul=body.surname_hangul, surname_hanja=body.surname_hanja,
                    given_hangul=body.given_hangul, given_hanja=body.given_hanja)
    return _finalize_envelope(data)


@router.get("/projects/{project_id}/finalize-check", response_model=Envelope[dict[str, Any]])
def project_finalize_check(project_id: str, db: Session = Depends(get_db)):
    p = ps.get_project(db, project_id)
    board = cb.current_board(db, project_id)
    if board is None or not board.chosen_candidate_id:
        raise AppError("결선에서 최종 이름을 먼저 결정하세요.")
    c = db.get(NameCandidate, board.chosen_candidate_id)
    data = fz.check(db, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja, given_hangul=c.given_hangul,
                    given_hanja=c.given_hanja or None)
    data["decision"] = {"id": board.id, "reason": board.reason, "decided_at": board.created_at.isoformat()}
    return _finalize_envelope(data)


def _finalize_envelope(data: dict):
    return envelope(data, verification_status=VerificationStatus.verified
                    if data["overall"] == "verified_against_loaded_data" else VerificationStatus.unverified,
                    warnings=[{"code": "not_a_filing_service", "message": fz.DISCLAIMER}])
