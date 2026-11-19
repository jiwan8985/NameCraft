"""양력↔음력(윤달) 변환 — CAL.LUNAR.v1.

구현체: `korean-lunar-calendar` (MIT, 한국천문연구원 자료 기반 표, SRC-KLC-LIB).
지원 범위: 양력 1391-02-05 ~ 2050-12-31. 범위 밖은 오류.
Golden Test(외부 기준값)와 일진 교차검증 통과 시에만 채택한다(DATA_SOURCES 권위 순위 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from korean_lunar_calendar import KoreanLunarCalendar

from namecraft.domain.calendar.errors import CalendarInputError, OutOfSupportedRange

LIB_ID = "korean-lunar-calendar==0.4.0"


@dataclass(frozen=True)
class LunarDate:
    year: int
    month: int
    day: int
    is_leap_month: bool

    def to_dict(self) -> dict:
        return {"year": self.year, "month": self.month, "day": self.day, "is_leap_month": self.is_leap_month,
                "text": f"{self.year}-{self.month:02d}-{self.day:02d}" + (" (윤달)" if self.is_leap_month else "")}


def solar_to_lunar(d: date) -> LunarDate:
    c = KoreanLunarCalendar()
    if not c.setSolarDate(d.year, d.month, d.day):
        raise OutOfSupportedRange("음력 변환 지원 범위 밖의 날짜입니다.", details={"date": "out_of_range"})
    return LunarDate(c.lunarYear, c.lunarMonth, c.lunarDay, bool(c.isIntercalation))


def lunar_to_solar(year: int, month: int, day: int, is_leap_month: bool) -> date:
    c = KoreanLunarCalendar()
    if not c.setLunarDate(year, month, day, is_leap_month):
        raise CalendarInputError("존재하지 않는 음력 날짜이거나 지원 범위 밖입니다.")
    solar = date(c.solarYear, c.solarMonth, c.solarDay)
    # 라이브러리가 윤달이 없는 달의 윤달 입력을 평달로 바꿔 받아들이는 경우를 차단: 역변환으로 확인
    back = solar_to_lunar(solar)
    if (back.year, back.month, back.day, back.is_leap_month) != (year, month, day, is_leap_month):
        raise CalendarInputError("존재하지 않는 음력 날짜입니다(윤달 여부 확인).",
                                 details={"is_leap_month": is_leap_month})
    return solar


def library_day_gapja(d: date) -> str:
    """교차검증용: 라이브러리가 계산한 일진(한자). 엔진의 JDN 공식과 독립된 구현."""
    c = KoreanLunarCalendar()
    c.setSolarDate(d.year, d.month, d.day)
    return c.getChineseGapJaString().split()[2][:2]
