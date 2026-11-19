"""성씨·한자 조회 API (기획서 §18: GET /surnames, GET /hanja) + 데이터 관리 조회."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import lexicon as svc
from namecraft_api.deps import get_db

router = APIRouter(tags=["lexicon"])


def _official_warnings(session: Session, items: list[dict]) -> list[dict]:
    w = []
    if not svc.official_data_loaded(session):
        w.append({"code": "official_data_missing",
                  "message": "공식 인명용 한자표가 아직 적재되지 않았습니다. 허용 여부는 '판정 불가'이며 대법원 조회로 확인해야 합니다."})
    if any(i.get("record_status") == "conflict" for i in items):
        w.append({"code": "source_conflict", "message": "출처 간 정보가 일치하지 않는 항목이 있습니다. 공식 자료를 우선합니다."})
    return w


def _overall(items: list[dict]) -> VerificationStatus:
    if items and all(i["official"]["status"] == svc.OFFICIAL_VERIFIED for i in items):
        return VerificationStatus.verified
    return VerificationStatus.unverified


@router.get("/hanja", response_model=Envelope[list[dict[str, Any]]])
def hanja_search(char: str | None = Query(None, max_length=2), reading: str | None = Query(None, max_length=4),
                 name_only: bool = False, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    if not char and not reading:
        raise AppError("char 또는 reading 중 하나는 필요합니다.")
    items = svc.search_hanja(db, char=char, reading=reading, name_only=name_only, limit=limit)
    sources = {r["source_id"] for i in items for r in i["readings"]} | {"SRC-UNIHAN"}
    return envelope(items, verification_status=_overall(items), warnings=_official_warnings(db, items),
                    provenance=svc.provenance_for(db, sources),
                    calculation_assumptions=["modern 획수는 Unihan kTotalStrokes(비공식). 성명학 원획은 Phase 4 규칙으로 별도 산출."])


@router.get("/hanja/{cp}", response_model=Envelope[dict[str, Any]])
def hanja_detail(cp: str, db: Session = Depends(get_db)):
    item = svc.get_hanja(db, cp)
    if not item:
        raise NotFound(f"한자 데이터 없음: {cp}")
    return envelope(item, verification_status=_overall([item]), warnings=_official_warnings(db, [item]),
                    provenance=svc.provenance_for(db, {r["source_id"] for r in item["readings"]} | {"SRC-UNIHAN"}))


@router.get("/surnames", response_model=Envelope[list[dict[str, Any]]])
def surname_search(q: str = Query(..., min_length=1, max_length=8), db: Session = Depends(get_db)):
    items = svc.search_surnames(db, q)
    warnings = [{"code": "surname_seed_unverified",
                 "message": "성씨 사전은 개발용 시드이며 공식 통계와 대조 전입니다."}] if items else [
        {"code": "surname_not_found", "message": "사전에 없는 성씨입니다. 임시 레코드로 입력할 수 있으나 확정 판정은 보류됩니다."}]
    if any(i["record_status"] == "conflict" for i in items):
        warnings.append({"code": "source_conflict", "message": "성씨 한자 독음이 Unihan 자료와 일치하지 않습니다."})
    return envelope(items, verification_status=VerificationStatus.unverified, warnings=warnings,
                    provenance=svc.provenance_for(db, {i["source_id"] for i in items}))


class ProvisionalSurnameIn(BaseModel):
    hangul: str = Field(min_length=1, max_length=4)
    hanja: str | None = Field(default=None, max_length=4)


@router.post("/surnames/provisional", response_model=Envelope[dict[str, Any]], status_code=201)
def surname_provisional(body: ProvisionalSurnameIn, db: Session = Depends(get_db)):
    try:
        item = svc.create_provisional_surname(db, body.hangul, body.hanja)
    except ValueError as e:
        raise AppError("성씨 형식이 올바르지 않습니다.", details={"field": str(e)}) from None
    db.commit()
    return envelope(item, verification_status=VerificationStatus.unverified,
                    warnings=[{"code": "provisional_record", "message": "임시 레코드 — 확정 판정 보류"}])


@router.get("/admin/data", response_model=Envelope[dict[str, Any]])
def admin_data(db: Session = Depends(get_db)):
    return envelope({"summary": svc.data_summary(db), "sources": svc.list_sources(db),
                     "releases": svc.list_releases(db)})
