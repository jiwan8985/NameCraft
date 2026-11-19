"""만세력·사주 계산 API (기획서 §18: POST /saju/calculate) + 절기 조회.

입력(출생정보)은 저장·로그하지 않는다 (기획서 §20).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, model_validator

from namecraft.domain.calendar import astronomy as astro
from namecraft.domain.calendar import lunar
from namecraft.domain.calendar.saju import PROFILE_ID, RULE_VERSION, BirthInput, SajuOptions, calculate
from namecraft.provenance import Envelope, VerificationStatus, envelope

router = APIRouter(tags=["saju"])

PROVENANCE = [
    {"source_id": "SRC-JPL-DE", "role": "절기(태양 황경) 계산 행성력", "ephemeris": astro.EPHEMERIS_ID},
    {"source_id": "SRC-KLC-LIB", "role": "양력↔음력 변환", "library": lunar.LIB_ID},
]
BASE_WARNINGS = [
    {"code": "draft_profile", "message": f"분석 프로필 {PROFILE_ID} {RULE_VERSION} 은 초안입니다."},
    {"code": "external_verification_pending",
     "message": "만세력 기준값의 한국천문연구원(KASI) 대조가 완료되지 않았습니다. 중요한 결정 전 공식 만세력으로 확인하세요."},
]


class SajuOptionsIn(BaseModel):
    true_solar_time: Literal["off", "longitude_only", "with_equation_of_time"] = "off"
    zi_convention: Literal["jojasi_next_day", "yajasi_same_day"] = "jojasi_next_day"


class SajuIn(BaseModel):
    calendar: Literal["solar", "lunar"] = "solar"
    date: dt.date
    is_leap_month: bool = False
    time: dt.time | None = None
    time_range: tuple[dt.time, dt.time] | None = None
    tz: str = Field(default="Asia/Seoul", max_length=64)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    options: SajuOptionsIn = SajuOptionsIn()

    @model_validator(mode="after")
    def _one_time_mode(self):
        if self.time is not None and self.time_range is not None:
            raise ValueError("time 과 time_range 는 함께 쓸 수 없습니다.")
        return self


@router.post("/saju/calculate", response_model=Envelope[dict[str, Any]])
def saju_calculate(body: SajuIn):
    b = BirthInput(body.calendar, body.date, body.is_leap_month, body.time, body.time_range, body.tz)
    o = SajuOptions(body.options.true_solar_time, body.options.zi_convention, body.longitude)
    result = calculate(b, o)
    warnings = list(BASE_WARNINGS)
    if result["mode"] != "exact_time":
        warnings.append({"code": "multiple_scenarios",
                         "message": f"출생 시각이 확정되지 않아 {len(result['segments'])}개 경우로 나누어 계산했습니다. 평균하지 않습니다."})
    for w in result["warnings"]:
        warnings.append({"code": w, "message": "일광절약시간 전환으로 같은 시각이 두 번 존재합니다. 앞의 시각으로 계산했습니다."})
    return envelope(result, rule_profile=PROFILE_ID, rule_version=RULE_VERSION,
                    calculation_assumptions=result["assumptions"], verification_status=VerificationStatus.calculated,
                    warnings=warnings, provenance=PROVENANCE)


@router.get("/calendar/solar-terms", response_model=Envelope[list[dict[str, Any]]])
def solar_terms(year: int = Query(..., ge=1900, le=2050), tz: str = Query("Asia/Seoul", max_length=64)):
    from namecraft.domain.calendar.saju import get_zone

    zone = get_zone(tz)
    data = [{"index": t["index"], "hangul": t["hangul"], "hanja": t["hanja"], "longitude": t["longitude"],
             "is_jeol": t["is_jeol"], "utc": t["instant_utc"].isoformat(timespec="seconds"),
             "local": t["instant_utc"].astimezone(zone).replace(tzinfo=None).isoformat(timespec="seconds")}
            for t in astro.solar_terms_of_year(year)]
    return envelope(data, verification_status=VerificationStatus.calculated, provenance=PROVENANCE[:1],
                    calculation_assumptions=["절입 시각 = 태양 겉보기 황경이 15°×k 를 지나는 순간 (초 단위 절사)"],
                    warnings=BASE_WARNINGS[1:])
