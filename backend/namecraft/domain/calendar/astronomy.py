"""천문 계산: 24절기 절입 시각, 진태양시 (CAL.SOLARTERM.v1, CAL.SOLARTIME.v1).

- 행성력: NASA JPL DE421에서 태양·지구 계산에 필요한 구간만 발췌한 파일
  (`datasets/ephemeris/de421-solar-terms-1900-2050.bsp`, 원본 SRC-JPL-DE).
- 절기 = 태양 겉보기 황경(그날의 춘분점 기준)이 15°×k 를 지나는 순간 (Skyfield almanac_east_asia).
- 지원 범위: 1900-01-01 ~ 2050-12-31 (발췌 파일 범위 안쪽).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from namecraft.config import REPO_ROOT
from namecraft.domain.calendar.errors import EphemerisUnavailable, OutOfSupportedRange

EPHEMERIS_PATH = REPO_ROOT / "datasets" / "ephemeris" / "de421-solar-terms-1900-2050.bsp"
EPHEMERIS_ID = "de421-excerpt-1900-2050"
SUPPORTED_FROM = datetime(1900, 1, 1, tzinfo=UTC)
SUPPORTED_TO = datetime(2051, 1, 1, tzinfo=UTC)

# index 0 = 춘분(0°), 15° 간격. Skyfield SOLAR_TERMS 와 동일한 순서.
TERMS_HANJA = ["春分", "淸明", "穀雨", "立夏", "小滿", "芒種", "夏至", "小暑", "大暑", "立秋", "處暑", "白露",
               "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至", "小寒", "大寒", "立春", "雨水", "驚蟄"]
TERMS_KO = ["춘분", "청명", "곡우", "입하", "소만", "망종", "하지", "소서", "대서", "입추", "처서", "백로",
            "추분", "한로", "상강", "입동", "소설", "대설", "동지", "소한", "대한", "입춘", "우수", "경칩"]
IPCHUN = 21
# 월주 경계가 되는 12절(節): 입춘·경칩·청명·입하·망종·소서·입추·백로·한로·입동·대설·소한
JEOL_INDICES = {21, 23, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19}


def check_range(dt: datetime) -> None:
    if not (SUPPORTED_FROM <= dt < SUPPORTED_TO):
        raise OutOfSupportedRange("지원 범위(1900-01-01 ~ 2050-12-31) 밖의 일시입니다.",
                                  details={"supported": ["1900-01-01", "2050-12-31"]})


@lru_cache(maxsize=1)
def _sky():
    try:
        from skyfield import almanac_east_asia
        from skyfield.api import load, load_file
    except ImportError as exc:  # pragma: no cover
        raise EphemerisUnavailable("skyfield 패키지가 설치되지 않았습니다.") from exc
    path = Path(EPHEMERIS_PATH)
    if not path.exists():
        raise EphemerisUnavailable("행성력 파일이 없습니다.", details={"path": str(path)})
    ts = load.timescale()  # 내장 ΔT/윤초 데이터 사용(다운로드 없음)
    eph = load_file(str(path))
    return ts, eph, almanac_east_asia.solar_terms(eph)


def term_index_at(dt: datetime) -> int:
    """dt 시점의 태양 황경이 속한 15° 구간 번호 (0=춘분~청명 사이)."""
    check_range(dt)
    ts, _, f = _sky()
    return int(f(ts.from_datetime(dt.astimezone(UTC))))


def terms_between(start: datetime, end: datetime) -> list[dict]:
    """[start, end) 사이 절입 시각 목록 (UTC)."""
    from skyfield.almanac import find_discrete

    check_range(start)
    check_range(end - timedelta(seconds=1))
    ts, _, f = _sky()
    times, idx = find_discrete(ts.from_datetime(start.astimezone(UTC)), ts.from_datetime(end.astimezone(UTC)), f)
    out = []
    for t, i in zip(times, idx):
        i = int(i)
        out.append({"index": i, "hanja": TERMS_HANJA[i], "hangul": TERMS_KO[i], "longitude": i * 15,
                    "is_jeol": i in JEOL_INDICES,
                    "instant_utc": t.utc_datetime().replace(microsecond=0)})
    return out


@lru_cache(maxsize=512)
def ipchun_instant(year: int) -> datetime:
    """해당 그레고리력 연도의 입춘 절입 시각(UTC)."""
    found = [t for t in terms_between(datetime(year, 1, 25, tzinfo=UTC), datetime(year, 2, 15, tzinfo=UTC))
             if t["index"] == IPCHUN]
    if len(found) != 1:  # pragma: no cover - 천문적으로 불가능
        raise RuntimeError(f"입춘 탐색 실패: {year}")
    return found[0]["instant_utc"]


def solar_terms_of_year(year: int) -> list[dict]:
    return terms_between(datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC))


# ---------------------------------------------------------------- 진태양시

def local_mean_time(dt_utc: datetime, longitude: float) -> datetime:
    """지방평균시 = UTC + 경도/15 시간 (naive datetime 반환)."""
    return (dt_utc.astimezone(UTC) + timedelta(hours=longitude / 15)).replace(tzinfo=None)


def apparent_solar_time(dt_utc: datetime, longitude: float) -> datetime:
    """진태양시 = 태양의 지방시각(시간각) + 12h. 행성력으로 직접 계산(균시차 포함)."""
    from skyfield.api import wgs84

    check_range(dt_utc)
    ts, eph, _ = _sky()
    t = ts.from_datetime(dt_utc.astimezone(UTC))
    obs = eph["earth"] + wgs84.latlon(0.0, longitude)
    ha, _, _ = obs.at(t).observe(eph["sun"]).apparent().hadec()
    hours = (ha.hours + 12.0) % 24.0
    lmt = local_mean_time(dt_utc, longitude)
    # LMT 날짜를 기준으로, 진태양시와 LMT 차이(균시차, ±17분 이내)가 가장 작은 날짜를 선택
    base = datetime.combine(lmt.date(), datetime.min.time()) + timedelta(hours=hours)
    return min((base + timedelta(days=d) for d in (-1, 0, 1)), key=lambda x: abs((x - lmt).total_seconds()))


def jdn(d: date) -> int:
    return d.toordinal() + 1721425


def equation_of_time_minutes(dt_utc: datetime, longitude: float) -> float:
    return (apparent_solar_time(dt_utc, longitude) - local_mean_time(dt_utc, longitude)).total_seconds() / 60


__all__ = ["TERMS_HANJA", "TERMS_KO", "IPCHUN", "JEOL_INDICES", "term_index_at", "terms_between",
           "ipchun_instant", "solar_terms_of_year", "local_mean_time", "apparent_solar_time", "jdn",
           "equation_of_time_minutes", "check_range", "EPHEMERIS_ID"]
