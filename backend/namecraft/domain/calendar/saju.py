"""사주 4주(연·월·일·시) 계산과 시간 범위 시나리오 분할 (기획서 §6.1, §11).

규칙 ID와 프로필 옵션은 docs/ANALYSIS_RULES.md §2 참조. 해석(용신 등)은 포함하지 않는다.

시간 기준
- 연주·월주: 절입 **순간(UTC)** 과 출생 순간 비교 → 지역 시각 체계와 무관.
- 일주·시주: "유효 지방시" 기준.
    true_solar_time=off              → 해당 지역 **표준시**(일광절약시간 제거, 역사적 표준시 반영)
    true_solar_time=longitude_only   → 지방평균시 = UTC + 경도/15h
    true_solar_time=with_equation_of_time → 진태양시(지방평균시 + 균시차)
- 자시: jojasi_next_day(23시부터 다음 날 일주) | yajasi_same_day(23–24시는 당일 일주, 시간은 다음 날 기준)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from namecraft.domain.calendar import ENGINE_VERSION
from namecraft.domain.calendar import astronomy as astro
from namecraft.domain.calendar import lunar
from namecraft.domain.calendar.errors import CalendarInputError
from namecraft.domain.calendar.ganzhi import (
    Pillar,
    day_pillar_from_jdn,
    element_counts,
    hour_branch_from_hours,
    hour_pillar,
    month_pillar,
    year_pillar,
)

PROFILE_ID = "kr-common-2026"
RULE_VERSION = "0.1.0-draft"
TRUE_SOLAR_MODES = ("off", "longitude_only", "with_equation_of_time")
ZI_CONVENTIONS = ("jojasi_next_day", "yajasi_same_day")
SCAN_STEP = timedelta(minutes=10)
BOUNDARY_PRECISION = timedelta(seconds=1)


@dataclass(frozen=True)
class SajuOptions:
    true_solar_time: str = "off"
    zi_convention: str = "jojasi_next_day"
    longitude: float | None = None

    def __post_init__(self):
        if self.true_solar_time not in TRUE_SOLAR_MODES:
            raise CalendarInputError("true_solar_time 옵션 오류", details={"allowed": TRUE_SOLAR_MODES})
        if self.zi_convention not in ZI_CONVENTIONS:
            raise CalendarInputError("zi_convention 옵션 오류", details={"allowed": ZI_CONVENTIONS})
        if self.true_solar_time != "off" and self.longitude is None:
            raise CalendarInputError("진태양시 계산에는 출생지 경도(longitude)가 필요합니다.")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise CalendarInputError("경도 범위 오류")


@dataclass
class Chart:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None
    effective_local: datetime
    saju_year: int
    month_no: int
    is_late_zi: bool = False  # 23–24시 자시

    @property
    def key(self) -> tuple:
        return (self.year.index, self.month.index, self.day.index, self.hour.index if self.hour else None)

    def to_dict(self) -> dict:
        pillars = [p for p in (self.year, self.month, self.day, self.hour) if p is not None]
        return {
            "pillars": {"year": self.year.to_dict(), "month": self.month.to_dict(), "day": self.day.to_dict(),
                        "hour": self.hour.to_dict() if self.hour else None},
            "text": " ".join(p.hanja for p in pillars),
            "day_master": self.day.to_dict()["stem"],
            "element_counts": element_counts(pillars),
            "element_counts_basis": "천간·지지 표면 오행(지장간 미포함)" + ("" if self.hour else ", 시주 제외"),
            "saju_year": self.saju_year,
            "month_branch_index": self.month_no,
            "is_late_zi_hour": self.is_late_zi,
        }


# ---------------------------------------------------------------- time helpers

def get_zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise CalendarInputError("알 수 없는 시간대입니다.", details={"tz": tz}) from None


def local_to_utc(local: datetime, zone: ZoneInfo) -> tuple[datetime, list[str]]:
    """naive 지역 시각 → UTC. 일광절약시간 전환으로 없는/중복된 시각을 감지한다."""
    warnings = []
    a = local.replace(tzinfo=zone, fold=0)
    b = local.replace(tzinfo=zone, fold=1)
    if a.utcoffset() != b.utcoffset():
        back = a.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if back != local:
            raise CalendarInputError("해당 지역에 존재하지 않는 시각입니다(일광절약시간 전환).",
                                     details={"reason": "nonexistent_local_time"})
        warnings.append("ambiguous_local_time")  # 같은 벽시계 시각이 두 번 존재 — 첫 번째로 계산
    return a.astimezone(UTC), warnings


def effective_local(dt_utc: datetime, zone: ZoneInfo, opts: SajuOptions) -> datetime:
    if opts.true_solar_time == "longitude_only":
        return astro.local_mean_time(dt_utc, opts.longitude)  # type: ignore[arg-type]
    if opts.true_solar_time == "with_equation_of_time":
        return astro.apparent_solar_time(dt_utc, opts.longitude)  # type: ignore[arg-type]
    loc = dt_utc.astimezone(zone)
    std = loc.utcoffset() - (loc.dst() or timedelta(0))
    return (dt_utc + std).replace(tzinfo=None)


# ---------------------------------------------------------------- chart

def chart_at(dt_utc: datetime, zone: ZoneInfo, opts: SajuOptions, *, with_hour: bool = True) -> Chart:
    astro.check_range(dt_utc)
    # 월주: 태양 황경 구간 → 寅월(입춘 315°)부터 30° 단위
    month_no = ((astro.term_index_at(dt_utc) - astro.IPCHUN) % 24) // 2
    # 연주: 입춘 기준. 같은 황경 값에서 유도해 월주와 경계가 정확히 일치하도록 한다.
    # 子월(10)은 12월~1월, 丑월(11)은 1~2월에 걸치므로 1·2월이면 전년도.
    saju_year = dt_utc.year - 1 if (month_no >= 10 and dt_utc.month <= 2) else dt_utc.year
    yp = year_pillar(saju_year)
    mp = month_pillar(yp.stem, month_no)
    # 일주·시주: 유효 지방시
    eff = effective_local(dt_utc, zone, opts)
    hours = eff.hour + eff.minute / 60 + eff.second / 3600
    late_zi = hours >= 23
    day_date = eff.date()
    if late_zi and opts.zi_convention == "jojasi_next_day":
        day_date += timedelta(days=1)
    dp = day_pillar_from_jdn(astro.jdn(day_date))
    hp = None
    if with_hour:
        stem_day = dp
        if late_zi and opts.zi_convention == "yajasi_same_day":
            stem_day = day_pillar_from_jdn(astro.jdn(eff.date() + timedelta(days=1)))
        hp = hour_pillar(stem_day.stem, hour_branch_from_hours(hours))
    return Chart(yp, mp, dp, hp, eff, saju_year, month_no, late_zi)


# ---------------------------------------------------------------- scenario segmentation

@dataclass
class Segment:
    start_utc: datetime
    end_utc: datetime  # 배타적 끝
    chart: Chart
    causes: list[str] = field(default_factory=list)  # 이 구간이 시작된 이유(직전 구간 대비 바뀐 기둥)


def _first_change(f, a: datetime, b: datetime, key_a) -> datetime:
    """key(a) == key_a, key(b) != key_a 일 때 첫 변화 시점(1초 정밀도)."""
    while b - a > BOUNDARY_PRECISION:
        mid = a + (b - a) / 2
        if f(mid) == key_a:
            a = mid
        else:
            b = mid
    # 변화 지점은 (a, b]. 새 값이 처음 나타나는 '정수 초'를 경계로 보고한다.
    floor_b = b.replace(microsecond=0)
    return floor_b if floor_b > a and f(floor_b) != key_a else floor_b + timedelta(seconds=1)


def segment_range(start_utc: datetime, end_utc: datetime, zone: ZoneInfo, opts: SajuOptions) -> list[Segment]:
    """[start, end) 를 4주 중 하나라도 바뀌는 지점에서 분할. 값을 평균하지 않는다(기획서 §11)."""
    if end_utc <= start_utc:
        raise CalendarInputError("시간 범위의 끝이 시작보다 늦어야 합니다.")
    if end_utc - start_utc > timedelta(days=62):
        raise CalendarInputError("한 번에 계산할 수 있는 범위는 최대 62일입니다.")

    def key(t: datetime):
        return chart_at(t, zone, opts).key

    segments: list[Segment] = []
    cur, cur_key = start_utc, key(start_utc)
    probe = start_utc
    while probe < end_utc:
        nxt = min(probe + SCAN_STEP, end_utc)
        k = key(nxt) if nxt < end_utc else key(end_utc - timedelta(seconds=1))
        if k != cur_key:
            change = _first_change(key, probe, nxt if nxt < end_utc else end_utc - timedelta(seconds=1), cur_key)
            segments.append(Segment(cur, change, chart_at(cur, zone, opts)))
            cur, cur_key = change, key(change)
            probe = change
            continue
        probe = nxt
    segments.append(Segment(cur, end_utc, chart_at(cur, zone, opts)))
    names = ("year", "month", "day", "hour")
    for prev, seg in zip(segments, segments[1:]):
        seg.causes = [n for n, a, b in zip(names, prev.chart.key, seg.chart.key) if a != b]
    return segments


# ---------------------------------------------------------------- public entry

@dataclass
class BirthInput:
    calendar: str  # solar | lunar
    date: date | tuple[int, int, int]
    is_leap_month: bool = False
    time: time | None = None
    time_range: tuple[time, time] | None = None  # 같은 날짜 내 [start, end), end=00:00 이면 자정까지
    tz: str = "Asia/Seoul"


def resolve_solar_date(b: BirthInput) -> date:
    if b.calendar == "solar":
        if b.is_leap_month:
            raise CalendarInputError("양력 날짜에는 윤달 옵션을 쓸 수 없습니다.")
        return b.date if isinstance(b.date, date) else date(*b.date)
    if b.calendar == "lunar":
        y, m, d = (b.date.year, b.date.month, b.date.day) if isinstance(b.date, date) else b.date
        return lunar.lunar_to_solar(y, m, d, b.is_leap_month)
    raise CalendarInputError("calendar 는 solar 또는 lunar 입니다.")


def assumptions(opts: SajuOptions, tz: str) -> list[str]:
    a = [
        "연주: 입춘 절입 순간 기준 (SAJU.YEAR.v1)",
        "월주: 12절 절입 순간 기준, 오호둔 (SAJU.MONTH.v1)",
        "일주: (JDN + 49) mod 60, 유효 지방시 날짜 기준 (SAJU.DAY.v1)",
        "시주: 2시간 단위 지지, 오서둔 (SAJU.HOUR.v1)",
        f"절기: JPL DE421 행성력 기반 태양 겉보기 황경 계산 ({astro.EPHEMERIS_ID})",
        {"jojasi_next_day": "자시: 23시부터 다음 날 일주(조자시 기준)",
         "yajasi_same_day": "자시: 23–24시는 당일 일주·다음 날 기준 시간(야자시 기준)"}[opts.zi_convention],
    ]
    if opts.true_solar_time == "off":
        a.append(f"시각 기준: {tz} 표준시(일광절약시간 제거, 역사적 표준시 변경 반영), 진태양시 미적용")
    elif opts.true_solar_time == "longitude_only":
        a.append(f"시각 기준: 지방평균시(경도 {opts.longitude}°), 균시차 미적용")
    else:
        a.append(f"시각 기준: 진태양시(경도 {opts.longitude}°, 균시차 포함)")
    return a


def calculate(b: BirthInput, opts: SajuOptions) -> dict:
    zone = get_zone(b.tz)
    solar = resolve_solar_date(b)
    warnings: list[str] = []

    if b.time is not None and b.time_range is not None:
        raise CalendarInputError("time 과 time_range 는 함께 쓸 수 없습니다.")

    if b.time is not None:
        utc, w = local_to_utc(datetime.combine(solar, b.time), zone)
        warnings += w
        chart = chart_at(utc, zone, opts)
        segs = [Segment(utc, utc, chart)]
        mode = "exact_time"
    else:
        if b.time_range is None:
            start_t, end_t, mode = time(0, 0), time(0, 0), "time_unknown"
        else:
            (start_t, end_t), mode = b.time_range, "time_range"
        start_local = datetime.combine(solar, start_t)
        end_local = datetime.combine(solar + timedelta(days=1) if end_t == time(0, 0) else solar, end_t)
        s_utc, w1 = local_to_utc(start_local, zone)
        e_utc, w2 = local_to_utc(end_local, zone)
        warnings += w1 + w2
        segs = segment_range(s_utc, e_utc, zone, opts)

    terms = astro.terms_between(segs[0].start_utc - timedelta(days=16), segs[-1].end_utc + timedelta(days=16))
    jeol = [t for t in terms if t["is_jeol"]]

    def fmt(dt: datetime) -> str:
        return dt.astimezone(zone).replace(tzinfo=None).isoformat(timespec="seconds")

    return {
        "mode": mode,
        "input": {"calendar": b.calendar, "solar_date": solar.isoformat(),
                  "lunar_date": lunar.solar_to_lunar(solar).to_dict(), "tz": b.tz},
        "options": {"true_solar_time": opts.true_solar_time, "zi_convention": opts.zi_convention,
                    "longitude": opts.longitude},
        "segments": [{
            "from_local": fmt(s.start_utc), "to_local": fmt(s.end_utc),
            "from_utc": s.start_utc.isoformat(timespec="seconds"), "to_utc": s.end_utc.isoformat(timespec="seconds"),
            "effective_local_start": s.chart.effective_local.isoformat(timespec="seconds"),
            "changed": s.causes, **s.chart.to_dict(),
        } for s in segs],
        "nearby_jeol": [{"hangul": t["hangul"], "hanja": t["hanja"], "local": fmt(t["instant_utc"]),
                         "utc": t["instant_utc"].isoformat()} for t in jeol],
        "assumptions": assumptions(opts, b.tz),
        "warnings": warnings,
        "engine_version": ENGINE_VERSION,
        "profile_id": PROFILE_ID,
        "rule_version": RULE_VERSION,
    }
