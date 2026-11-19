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


# ---------------------------------------------------------------- Phase 6: 생성·역검색

from typing import Literal  # noqa: E402

from namecraft.services.generation import GenerateRequest, GenerationError, generate  # noqa: E402
from namecraft.services.reverse_search import ReverseSearchError, alternative_hanja, reverse_search  # noqa: E402

GATE_WARNING = {"code": "official_gate_on_hold",
                "message": "공식 인명용 한자표가 적재되지 않아 한자 조합은 '보류'로 분류됩니다. 출생신고 전 대법원 조회로 확인하세요."}


class GenerateIn(BaseModel):
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    sex: Literal["m", "f", "n"] = "n"
    syllables: int = Field(default=2, ge=1, le=3)
    name_type: Literal["hanja", "hangul", "any"] = "hanja"
    include_syllables: list[str] = Field(default_factory=list, max_length=20)
    exclude_syllables: list[str] = Field(default_factory=list, max_length=50)
    exclude_initials: list[str] = Field(default_factory=list, max_length=19)
    exclude_hanja: list[str] = Field(default_factory=list, max_length=50)
    fixed_syllable: dict[int, str] = Field(default_factory=dict)
    fixed_hanja: dict[int, str] = Field(default_factory=dict)
    style_tags: dict[Literal["modern", "traditional", "soft", "bright"], float] = Field(default_factory=dict)
    liked_examples: list[str] = Field(default_factory=list, max_length=30)
    exclude_names: list[str] = Field(default_factory=list, max_length=500)
    count: int = Field(default=30, ge=1, le=200)
    diversity_threshold: float = Field(default=0.8, gt=0, le=1)
    use_traditional: bool = True


@router.post("/generate", response_model=Envelope[dict[str, Any]])
def names_generate(body: GenerateIn, db: Session = Depends(get_db)):
    try:
        data = generate(db, GenerateRequest(**body.model_dump()))
    except (GenerationError, ReverseSearchError) as e:
        raise AppError(str(e)) from None
    warnings = [{"code": "rule_based_generation",
                 "message": "규칙 기반 생성 결과입니다. 생성 점수는 후보를 고르기 위한 보조 지표이며 이름의 좋고 나쁨이 아닙니다."}]
    if data["on_hold"]:
        warnings.append(GATE_WARNING)
    if data["quarantined"]:
        warnings.append({"code": "quarantined", "message": "부정 연상 표현과 정확히 일치한 후보는 별도로 격리했습니다."})
    return envelope(data, verification_status=VerificationStatus.calculated, warnings=warnings,
                    calculation_assumptions=["후보 재료: 개발자 큐레이션 음절 사전·한글 이름 예시(빈도 통계 아님)",
                                             "성별은 선호 가중치일 뿐 제한 조건이 아님",
                                             "한자 제안: 인명용 독음 힌트(Unihan) 기반 역검색"],
                    provenance=[{"source_id": "SRC-DEV-NAME-SYLLABLES", "role": "음절 사전"},
                                {"source_id": "SRC-UNIHAN", "role": "한자 독음·획수"}])


class ReverseSearchIn(BaseModel):
    given_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    fixed_hanja: dict[int, str] = Field(default_factory=dict)
    exclude_hanja: list[str] = Field(default_factory=list, max_length=50)
    weights: dict[Literal["common_hanja", "no_meaning_caution", "luck81", "yinyang_balance"], float] = \
        Field(default_factory=dict)
    use_traditional: bool = True
    include_compat: bool = False
    limit: int = Field(default=30, ge=1, le=200)


@router.post("/reverse-search", response_model=Envelope[dict[str, Any]])
def names_reverse_search(body: ReverseSearchIn, db: Session = Depends(get_db)):
    try:
        data = reverse_search(db, given_hangul=body.given_hangul, surname_hanja=body.surname_hanja,
                              fixed=body.fixed_hanja, exclude_hanja=body.exclude_hanja, weights=body.weights,
                              use_traditional=body.use_traditional, include_compat=body.include_compat,
                              limit=body.limit)
    except ReverseSearchError as e:
        raise AppError(str(e)) from None
    warnings = []
    if data["impossible_syllables"]:
        warnings.append({"code": "no_name_hanja",
                         "message": f"인명용 독음 한자를 찾지 못한 음절: {''.join(data['impossible_syllables'])} — 한글 이름으로 쓸 수 있습니다."})
    if data.get("counts", {}).get("on_hold"):
        warnings.append(GATE_WARNING)
    if body.use_traditional:
        warnings.append({"code": "traditional_interpretation",
                         "message": "81수리·음양 항목은 전통 해석 · 출처 대조 전 자료로 정렬에 반영했습니다(가중치 조정 가능)."})
    return envelope(data, verification_status=VerificationStatus.unverified, warnings=warnings,
                    calculation_assumptions=["조합 정렬 점수 = 가중 평균(교육용 한자, 뜻 주의 없음, 81수리, 음양 조화). 계산 불가 항목은 제외 후 재정규화"],
                    provenance=[{"source_id": "SRC-UNIHAN", "role": "독음·획수·영어 풀이"},
                                {"source_id": "SRC-NUM-TRAD", "role": "81수리 통용 분류", "status": "source_check_pending"}])


class AlternativeIn(BaseModel):
    given_hangul: str = Field(min_length=1, max_length=4)
    given_hanja: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    use_traditional: bool = True


@router.post("/alternative-hanja", response_model=Envelope[dict[str, Any]])
def names_alternative_hanja(body: AlternativeIn, db: Session = Depends(get_db)):
    try:
        data = alternative_hanja(db, given_hangul=body.given_hangul, given_hanja=body.given_hanja,
                                 surname_hanja=body.surname_hanja, use_traditional=body.use_traditional)
    except ReverseSearchError as e:
        raise AppError(str(e)) from None
    return envelope(data, verification_status=VerificationStatus.unverified, warnings=[GATE_WARNING])


# ---------------------------------------------------------------- Phase 8: 비교

from namecraft.services.ranking import RankingError, rank_names  # noqa: E402


class CompareIn(BaseModel):
    surname_hangul: str = Field(min_length=1, max_length=4)
    surname_hanja: str | None = Field(default=None, max_length=4)
    names: list[dict] = Field(min_length=2, max_length=10)
    weights: dict[str, float] | None = None


@router.post("/compare", response_model=Envelope[dict[str, Any]])
def names_compare(body: CompareIn, db: Session = Depends(get_db)):
    """기획서 §18 POST /names/compare — 같은 기준으로 2~10개 이름 비교 + 쌍별 유사도."""
    for n in body.names:
        if not isinstance(n.get("given_hangul"), str) or not n["given_hangul"]:
            raise AppError("각 항목에 given_hangul 이 필요합니다.")
    try:
        ranked = rank_names(db, surname_hangul=body.surname_hangul, surname_hanja=body.surname_hanja,
                            names=[{"given_hangul": n["given_hangul"], "given_hanja": n.get("given_hanja")}
                                   for n in body.names], weights=body.weights)
        sim = compare_similarity(body.names)
    except (RankingError, NameInputError, ValueError) as e:
        raise AppError(str(e)) from None
    return envelope({**ranked, "similarity": sim}, verification_status=VerificationStatus.calculated,
                    warnings=[{"code": "comparison_basis",
                               "message": "모든 이름을 같은 가중치·학파 프로필로 비교했습니다. 전통 해석 항목은 상대 평가입니다."}])
