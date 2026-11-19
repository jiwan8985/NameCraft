"""이름 정밀 분석 API (기획서 §18: POST /names/analyze) + 후보 유사도."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from namecraft.domain.numerology.core import PROFILE_ID, RULE_VERSION, NumerologyOptions
from namecraft.errors import AppError
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services.name_analysis import analyze_full, compare_similarity
from namecraft.services.numerology import NameInputError
from namecraft_api.deps import get_db
from namecraft_api.routers.numerology import DISCLAIMER, SOURCE_PENDING, NumerologyOptionsIn

router = APIRouter(prefix="/names", tags=["names"])


class AnalyzeIn(BaseModel):
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    given_hangul: str = Field(min_length=1, max_length=6)
    given_hanja: str | None = Field(default=None, max_length=6)
    numerology_options: NumerologyOptionsIn = NumerologyOptionsIn()


@router.post("/analyze", response_model=Envelope[dict[str, Any]])
def analyze(body: AnalyzeIn, db: Session = Depends(get_db)):
    try:
        data = analyze_full(db, surname_hangul=body.surname_hangul, surname_hanja=body.surname_hanja,
                            given_hangul=body.given_hangul, given_hanja=body.given_hanja,
                            numerology_options=NumerologyOptions(**body.numerology_options.model_dump()))
    except NameInputError as e:
        raise AppError(str(e), details={"field": "name"}) from None
    warnings = list(data["numerology"].pop("warnings", []))
    if data["numerology"]["applicability"]["numerology"] == "applicable":
        warnings = [DISCLAIMER, SOURCE_PENDING, *warnings]
    if data["caution"]["candidates"]:
        warnings.append({"code": "caution_candidates",
                         "message": "놀림·부정 연상 가능성이 있는 표현 후보가 있습니다. 직접 검토해 보세요(판정 아님)."})
    warnings.append({"code": "korean_meaning_unavailable",
                     "message": "한자의 한국어 뜻과 의미 조합 평가는 아직 제공되지 않습니다(영어 풀이만 참고)."})
    return envelope(data, rule_profile=PROFILE_ID, rule_version=RULE_VERSION, warnings=warnings,
                    verification_status=VerificationStatus.calculated,
                    calculation_assumptions=["발음: 표준발음법 주요 규칙 기반 추정",
                                             "로마자: 국어의 로마자 표기법(인명, 음운 변화 미반영)",
                                             "부정 연상·뜻 주의: 개발자 작성 소규모 목록 대조(후보)"],
                    provenance=[{"source_id": "SRC-DEV-LANG-RULES", "role": "주의 단어·로마자 참고"},
                                {"source_id": "SRC-UNIHAN", "role": "한자 영어 풀이"}])


class SimilarityIn(BaseModel):
    names: list[dict] = Field(min_length=2, max_length=50)


@router.post("/similarity", response_model=Envelope[list[dict[str, Any]]])
def similarity(body: SimilarityIn):
    for n in body.names:
        if not isinstance(n.get("given_hangul"), str) or not n["given_hangul"]:
            raise AppError("각 항목에 given_hangul 이 필요합니다.")
    try:
        data = compare_similarity(body.names)
    except ValueError:
        raise AppError("한글 표기가 올바르지 않습니다.") from None
    return envelope(data, verification_status=VerificationStatus.calculated)
