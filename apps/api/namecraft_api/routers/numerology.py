"""학파별 수리 계산 API (기획서 §18: POST /numerology/calculate)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from namecraft.domain.numerology.core import PROFILE_ID, RULE_VERSION, NumerologyOptions
from namecraft.errors import AppError
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services.numerology import NameInputError, analyze_name
from namecraft_api.deps import get_db

router = APIRouter(tags=["numerology"])

DISCLAIMER = {"code": "traditional_interpretation",
              "message": "수리·오행 길흉은 전통 해석이며 과학적 근거가 없습니다. 이름이 건강·성공·운명을 결정하지 않습니다."}
SOURCE_PENDING = {"code": "source_check_pending",
                  "message": "전통 해석 · 출처 대조 전 — 81수리 분류는 통용 분류를 정리한 것으로 특정 문헌과 대조하지 않았습니다."}


class NumerologyOptionsIn(BaseModel):
    stroke_system: Literal["original", "modern"] = "original"
    single_name_virtual_stroke: Literal["none", "plus_one"] = "none"
    eumryeong_school: Literal["modern-common", "hunmin-haerye"] = "modern-common"
    numeral_by_meaning: bool = False


class NumerologyIn(BaseModel):
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    given_hangul: str = Field(min_length=1, max_length=6)
    given_hanja: str | None = Field(default=None, max_length=6)
    options: NumerologyOptionsIn = NumerologyOptionsIn()


@router.post("/numerology/calculate", response_model=Envelope[dict[str, Any]])
def numerology_calculate(body: NumerologyIn, db: Session = Depends(get_db)):
    opts = NumerologyOptions(**body.options.model_dump())
    try:
        result = analyze_name(db, surname_hangul=body.surname_hangul, surname_hanja=body.surname_hanja,
                              given_hangul=body.given_hangul, given_hanja=body.given_hanja, opts=opts)
    except NameInputError as e:
        raise AppError(str(e), details={"field": "name"}) from None
    warnings = [DISCLAIMER, SOURCE_PENDING, *result.pop("warnings")]
    applicable = result["applicability"]["numerology"] == "applicable"
    assumptions = [f"획수 체계: {'성명학 원획(부수 본자 환원, STROKE.ORIGINAL.v1)' if opts.stroke_system == 'original' else '현대 필획'}",
                   "원형이정: 원=이름 합, 형=성+이름 첫자, 이=성+이름 나머지, 정=전체 (복성은 합산)",
                   "81 초과 수는 80을 빼서 환원", f"음령오행 학파: {opts.eumryeong_school}"]
    if not applicable:
        assumptions = [f"음령오행 학파: {opts.eumryeong_school}"]
    return envelope(result, rule_profile=PROFILE_ID, rule_version=RULE_VERSION, calculation_assumptions=assumptions,
                    verification_status=VerificationStatus.traditional_interpretation if applicable
                    else VerificationStatus.not_applicable,
                    warnings=warnings,
                    provenance=[{"source_id": "SRC-UNIHAN", "role": "부수·획수 기초 자료"},
                                {"source_id": "SRC-NUM-TRAD", "role": "81수리 통용 분류", "status": "source_check_pending"}])
