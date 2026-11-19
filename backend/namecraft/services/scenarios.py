"""출생 예정일·시간 민감도 시뮬레이션 (기획서 §11, REQ-SIM-001~003).

- 예정일 ±N일 · 시간 구간 · 복수 후보 예정일 → 날짜별로 Phase 3 엔진 구간 분할 결과를 나열.
- 값을 평균하지 않는다: 경우별 명식, 바뀌는 기둥, 오행 개수의 최소·최대, 가정을 그대로 보여준다.
- 이름별 민감도는 '선택한 전통 해석(단순 보완설)'을 켰을 때만 계산하며, 사주와 무관한 항목(발음·수리 등)은
  출생 시각에 따라 달라지지 않는다는 점을 명시한다.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any

from namecraft.domain.calendar import ENGINE_VERSION
from namecraft.domain.calendar import interpretation as interp
from namecraft.domain.calendar.ganzhi import ELEMENTS
from namecraft.domain.calendar.saju import RULE_VERSION, BirthInput, SajuOptions, calculate, resolve_solar_date
from namecraft.errors import AppError

MAX_DATES = 15
MAX_WINDOW = 7


class ScenarioInputError(AppError):
    status_code = 422
    code = "scenario_input_invalid"


def scenario_dates(base_solar: date, day_window: int, extra_dates: list[date]) -> list[date]:
    if not 0 <= day_window <= MAX_WINDOW:
        raise ScenarioInputError(f"예정일 앞뒤 범위는 0~{MAX_WINDOW}일입니다.")
    ds = [base_solar + timedelta(days=d) for d in range(-day_window, day_window + 1)]
    ds += [d for d in extra_dates if d not in ds]
    if len(ds) > MAX_DATES:
        raise ScenarioInputError(f"한 번에 비교할 날짜는 최대 {MAX_DATES}개입니다.")
    return sorted(ds)


def evaluate(*, calendar: str, base_date: date, is_leap_month: bool, time_: time | None,
             time_range: tuple[time, time] | None, tz: str, longitude: float | None, true_solar_time: str,
             zi_convention: str, day_window: int = 0, extra_dates: list[date] | None = None,
             names: list[dict] | None = None) -> dict[str, Any]:
    """names: [{"label", "jawon": [오행|None,...]}] — 해석을 켰을 때만 전달."""
    opts = SajuOptions(true_solar_time, zi_convention, longitude)
    base_solar = resolve_solar_date(BirthInput(calendar, base_date, is_leap_month, None, None, tz))
    dates = scenario_dates(base_solar, day_window, extra_dates or [])

    scenarios: list[dict] = []
    for d in dates:
        r = calculate(BirthInput("solar", d, False, time_, time_range, tz), opts)
        for i, s in enumerate(r["segments"]):
            scenarios.append({
                "id": f"{d.isoformat()}#{i}", "date": d.isoformat(), "offset_days": (d - base_solar).days,
                "from_local": s["from_local"], "to_local": s["to_local"], "text": s["text"],
                "pillars": {k: (v["hanja"] if v else None) for k, v in s["pillars"].items()},
                "element_counts": s["element_counts"], "day_master": s["day_master"], "changed": s["changed"],
            })
        assumptions = r["assumptions"]

    # 바뀌는 기둥과 오행 범위 (평균 없음)
    varying = [k for k in ("year", "month", "day", "hour") if len({s["pillars"][k] for s in scenarios}) > 1]
    ranges = {e: {"min": min(s["element_counts"][e] for s in scenarios),
                  "max": max(s["element_counts"][e] for s in scenarios)} for e in ELEMENTS}
    distinct_charts = len({s["text"] for s in scenarios})

    name_results = []
    for n in names or []:
        per = []
        for s in scenarios:
            c = interp.complement_score(s["element_counts"], n["jawon"])
            per.append({"scenario_id": s["id"], "score": c["score"], "weak": c["weak"]})
        scores = [p["score"] for p in per if p["score"] is not None]
        name_results.append({
            "label": n["label"], "candidate_id": n.get("candidate_id"),
            "per_scenario": per,
            "min": min(scores) if scores else None, "max": max(scores) if scores else None,
            "sensitivity": interp.sensitivity_label(scores) if scores else "not_available",
            "profile_id": interp.PROFILE_ID,
        })

    return {
        "base_solar_date": base_solar.isoformat(), "dates": [d.isoformat() for d in dates],
        "scenarios": scenarios, "scenario_count": len(scenarios), "distinct_charts": distinct_charts,
        "varying_pillars": varying, "element_ranges": ranges,
        "names": name_results,
        "interpretation": {"enabled": names is not None, "profile_id": interp.PROFILE_ID,
                           "disclaimer": interp.DISCLAIMER},
        "notes": ["시나리오별 값을 평균하지 않습니다. 각 경우의 명식과 범위를 함께 확인하세요.",
                  "발음·의미·수리·사용성 점수는 출생 시각과 무관하여 시나리오에 따라 달라지지 않습니다."],
        "assumptions": assumptions, "engine_version": ENGINE_VERSION, "rule_version": RULE_VERSION,
    }
