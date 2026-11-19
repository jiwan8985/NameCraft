"""속성 기반 테스트 (기획서 §22.1): 결정론·교차검증·경계 일관성."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given, settings, strategies as st

from namecraft.domain.calendar import astronomy as astro
from namecraft.domain.calendar import lunar
from namecraft.domain.calendar.errors import OutOfSupportedRange
from namecraft.domain.calendar.ganzhi import Pillar, day_pillar_from_jdn, hour_branch_from_hours, month_pillar
from namecraft.domain.calendar.saju import BirthInput, SajuOptions, calculate, chart_at

SEOUL = ZoneInfo("Asia/Seoul")
dates = st.dates(min_value=date(1900, 2, 1), max_value=date(2050, 12, 30))


@given(dates)
@settings(max_examples=300, deadline=None)
def test_day_pillar_matches_independent_library(d):
    """엔진의 JDN 공식 ↔ korean-lunar-calendar 일진: 서로 독립된 구현이 일치해야 한다."""
    assert day_pillar_from_jdn(astro.jdn(d)).hanja == lunar.library_day_gapja(d)


@given(dates)
@settings(max_examples=150, deadline=None)
def test_lunar_roundtrip(d):
    ld = lunar.solar_to_lunar(d)
    assert lunar.lunar_to_solar(ld.year, ld.month, ld.day, ld.is_leap_month) == d


@given(st.datetimes(min_value=datetime(1901, 1, 1), max_value=datetime(2050, 12, 1)))
@settings(max_examples=60, deadline=None)
def test_chart_deterministic_and_consistent(naive):
    utc = naive.replace(tzinfo=UTC)
    a = chart_at(utc, SEOUL, SajuOptions())
    b = chart_at(utc, SEOUL, SajuOptions())
    assert a.key == b.key  # 결정론
    # 월주 천간은 항상 연간 기준 오호둔 결과와 일치
    assert a.month == month_pillar(a.year.stem, a.month_no)


def test_pillar_of_rejects_parity_mismatch():
    import pytest

    with pytest.raises(ValueError):
        Pillar.of(0, 1)


def test_hour_branch_edges():
    assert hour_branch_from_hours(23.0) == 0 and hour_branch_from_hours(0.99) == 0
    assert hour_branch_from_hours(1.0) == 1 and hour_branch_from_hours(22.99) == 11


def test_each_year_has_24_terms_with_12_jeol():
    for y in (1900, 1988, 2027, 2050):
        terms = astro.solar_terms_of_year(y)
        assert len(terms) == 24 and sum(t["is_jeol"] for t in terms) == 12


def test_out_of_range_rejected():
    import pytest

    with pytest.raises(OutOfSupportedRange):
        calculate(BirthInput("solar", date(1899, 12, 31), time=time(12)), SajuOptions())


def test_segments_are_contiguous_and_cover_range():
    r = calculate(BirthInput("solar", date(2027, 2, 4)), SajuOptions(true_solar_time="with_equation_of_time",
                                                                      longitude=126.978))
    segs = r["segments"]
    assert segs[0]["from_local"] == "2027-02-04T00:00:00" and segs[-1]["to_local"] == "2027-02-05T00:00:00"
    for a, b in zip(segs, segs[1:]):
        assert a["to_utc"] == b["from_utc"] and a["text"] != b["text"]


def test_true_solar_offset_matches_longitude():
    utc = datetime(2027, 1, 15, 1, 0, tzinfo=UTC)
    lmt = astro.local_mean_time(utc, 126.978)
    assert abs((lmt - datetime(2027, 1, 15, 9, 27, 55)).total_seconds()) < 1
    eot = astro.equation_of_time_minutes(utc, 126.978)
    assert -10.5 < eot < -8.0  # 1월 중순 균시차 약 −9분 (천문 상식 범위 확인)
