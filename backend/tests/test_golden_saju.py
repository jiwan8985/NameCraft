"""datasets/golden-tests/saju.yaml 실행기 (기획서 §22.1 Golden/reference)."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
import yaml

from namecraft.config import REPO_ROOT
from namecraft.domain.calendar import astronomy as astro
from namecraft.domain.calendar import lunar
from namecraft.domain.calendar.errors import CalendarInputError
from namecraft.domain.calendar.ganzhi import day_pillar_from_jdn
from namecraft.domain.calendar.saju import BirthInput, SajuOptions, calculate

pytestmark = pytest.mark.golden

DOC = yaml.safe_load((REPO_ROOT / "datasets" / "golden-tests" / "saju.yaml").read_text(encoding="utf-8"))
CASES = [pytest.param(c, id=c["id"]) for c in DOC["cases"]]


def _t(s: str) -> time:
    return time.fromisoformat(s)


def _birth(i: dict) -> tuple[BirthInput, SajuOptions]:
    rng = tuple(_t(x) for x in i["time_range"]) if "time_range" in i else None
    b = BirthInput("solar", date.fromisoformat(i["date"]), time=_t(i["time"]) if "time" in i else None,
                   time_range=rng, tz=i.get("tz", "Asia/Seoul"))
    return b, SajuOptions(**i.get("options", {}))


def _secs(hms: str) -> int:
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s


@pytest.mark.parametrize("case", CASES)
def test_golden(case):
    if case["status"] == "pending":
        pytest.skip("pending — 통과로 집계하지 않음")
    kind, i, exp = case["kind"], case["input"], case["expected"]

    if kind == "day_pillar":
        d = date.fromisoformat(i["date"])
        assert day_pillar_from_jdn(astro.jdn(d)).hanja == exp["day_pillar"]
        if "jdn" in exp:
            assert astro.jdn(d) == exp["jdn"]
        if "SRC-KLC-LIB" in case.get("cross_checks", []):
            assert lunar.library_day_gapja(d) == exp["day_pillar"]

    elif kind == "solar_term":
        terms = [t for t in astro.solar_terms_of_year(i["year"]) if t["hangul"] == i["term"]]
        local = terms[0]["instant_utc"].astimezone(ZoneInfo(exp["tz"]))
        assert local.strftime("%Y-%m-%dT%H:%M") == exp["local"]

    elif kind == "solar_to_lunar":
        got = lunar.solar_to_lunar(date.fromisoformat(i["date"]))
        assert (got.year, got.month, got.day, got.is_leap_month) == (exp["year"], exp["month"], exp["day"],
                                                                     exp["is_leap_month"])

    elif kind == "lunar_to_solar":
        if "error" in exp:
            with pytest.raises(CalendarInputError):
                lunar.lunar_to_solar(i["year"], i["month"], i["day"], i["is_leap_month"])
        else:
            assert lunar.lunar_to_solar(i["year"], i["month"], i["day"], i["is_leap_month"]).isoformat() == exp["date"]

    elif kind == "chart":
        b, o = _birth(i)
        if "error" in exp:
            with pytest.raises(CalendarInputError) as e:
                calculate(b, o)
            assert e.value.code == exp["error"]
            return
        seg = calculate(b, o)["segments"][0]
        assert seg["text"] == exp["text"]
        if "effective_local" in exp:
            assert seg["effective_local_start"] == exp["effective_local"]

    elif kind == "range":
        b, o = _birth(i)
        segs = calculate(b, o)["segments"]
        if "segments_count" in exp:
            assert len(segs) == exp["segments_count"]
            assert len({s["pillars"]["hour"]["branch"] for s in segs}) == exp["distinct_hour_branches"]
            return
        tol = case.get("tolerance_seconds", 0)
        assert len(segs) == len(exp["segments"])
        for s, e in zip(segs, exp["segments"]):
            assert abs(_secs(s["from_local"][11:]) - _secs(e["from"])) <= tol
            end = s["to_local"][11:]
            assert abs(_secs(end) - _secs(e["to"])) <= tol
            if "hour" in e:
                assert s["pillars"]["hour"]["hanja"] == e["hour"]
            if "text" in e:
                assert s["text"] == e["text"]
            if "changed" in e:
                assert s["changed"] == e["changed"]
    else:  # pragma: no cover
        pytest.fail(f"unknown kind {kind}")


def test_status_report():
    """Phase 3 완료 게이트 현황: externally_verified 케이스 수를 드러낸다(0이면 게이트 미충족)."""
    counts: dict[str, int] = {}
    for c in DOC["cases"]:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    assert sum(counts.values()) == len(DOC["cases"])
    print("\nsaju golden status:", counts)
