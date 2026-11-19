"""교차검증 (기획서 §13): 사람이 검토한 문서 값 ↔ 자체 계산.

목표는 해석의 참/거짓 판정이 아니라 '어떤 공식·입력·옵션이면 문서 값을 재현하는가' 확인이다.
결과 분류
  match               — 같은 값 (어떤 체계/옵션으로 재현되는지 함께 표시)
  numeric_difference  — 입력(획수 등)이 달라 값이 다름
  formula_difference  — 같은 입력으로도 우리 공식·옵션 조합으로 재현되지 않음
  source_difference   — 해석 표(81수리 등) 출처·학파 차이
  not_comparable      — 비교에 필요한 값 부족
"""

from __future__ import annotations

import itertools
from datetime import date, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import CrosscheckResult, Surname
from namecraft.domain.calendar import ENGINE_VERSION
from namecraft.domain.calendar.errors import CalendarInputError, OutOfSupportedRange
from namecraft.domain.calendar.saju import BirthInput, SajuOptions, calculate
from namecraft.domain.numerology.core import RULE_VERSION, four_gyeok, luck_of
from namecraft.domain.text import codepoint
from namecraft.services.imports import assertions_of, get_doc
from namecraft.services.lexicon import stroke_map

LUCK_KO = {"good": "길", "half": "반길", "bad": "흉"}
GYEOK_KO = {"won": "원격", "hyeong": "형격", "i": "이격", "jeong": "정격"}
SEOUL_LON = 126.978


def _values(session: Session, doc_id: str) -> dict[str, str]:
    out = {}
    for a in assertions_of(session, doc_id):
        if a.review_status in ("accepted", "corrected"):
            out[a.field] = a.corrected_value if a.review_status == "corrected" else a.value
    return out


def _surname_len(session: Session, hangul: str, project_surname: str | None) -> int:
    if project_surname and hangul.startswith(project_surname):
        return len(project_surname)
    if len(hangul) >= 3 and session.scalar(select(Surname.id).where(Surname.hangul == hangul[:2])):
        return 2  # 복성
    return 1


def run_crosscheck(session: Session, doc_id: str, *, project=None, birth_profile=None) -> CrosscheckResult:
    doc = get_doc(session, doc_id)
    v = _values(session, doc_id)
    items: list[dict[str, Any]] = []

    hanja = v.get("name_hanja")
    hangul = v.get("name_hangul")
    ours: dict[str, dict[str, int | None]] = {}
    if hanja:
        for ch in hanja:
            ours[ch] = stroke_map(session, codepoint(ch))

    # 1) 글자별 획수
    doc_strokes: dict[str, int] = {}
    for key, val in v.items():
        if not key.startswith("strokes:"):
            continue
        ch = key.split(":", 1)[1]
        try:
            n = int(val)
        except ValueError:
            items.append({"item": f"{ch} 획수", "result": "not_comparable", "doc": val, "detail": "숫자가 아님"})
            continue
        doc_strokes[ch] = n
        st = ours.get(ch) or stroke_map(session, codepoint(ch))
        systems = [s for s in ("original", "modern") if st.get(s) == n]
        items.append({"item": f"{ch} 획수", "doc": n, "ours": {"original": st.get("original"), "modern": st.get("modern")},
                      "result": "match" if systems else "numeric_difference",
                      "detail": (f"{'원획' if systems[0] == 'original' else '필획'} 기준과 일치" if systems
                                 else "원획·필획 모두와 다름 — 문서의 획수 기준(학파 예외·이체자 등) 확인 필요")})

    # 2) 원형이정 4격
    doc_gyeok = {k.split(".")[1]: int(val) for k, val in v.items() if k.startswith("gyeok.") and val.isdigit()}
    if doc_gyeok and hanja and hangul and len(hanja) == len(hangul):
        sl = _surname_len(session, hangul, project.surname_hangul if project else None)
        s_chars, g_chars = hanja[:sl], hanja[sl:]
        reproduced = []
        for system, virtual in itertools.product(("original", "modern"), ("none", "plus_one")):
            s = [ours[c].get(system) for c in s_chars]
            g = [ours[c].get(system) for c in g_chars]
            if None in s + g or not g:
                continue
            calc = four_gyeok(s, g, virtual=virtual)  # type: ignore[arg-type]
            if all(calc[k] == n for k, n in doc_gyeok.items()):
                reproduced.append({"stroke_system": system, "single_name_virtual_stroke": virtual})
        if reproduced:
            r = reproduced[0]
            items.append({"item": "원형이정 4격", "doc": doc_gyeok, "result": "match", "reproduced_by": reproduced,
                          "detail": f"{'원획' if r['stroke_system'] == 'original' else '필획'}·가수 "
                                    f"{'없음' if r['single_name_virtual_stroke'] == 'none' else '1'} 조건에서 재현"})
        elif doc_strokes and all(c in doc_strokes for c in hanja):
            calc = four_gyeok([doc_strokes[c] for c in s_chars], [doc_strokes[c] for c in g_chars])
            same = all(calc[k] == n for k, n in doc_gyeok.items())
            items.append({"item": "원형이정 4격", "doc": doc_gyeok, "ours_from_doc_strokes": calc,
                          "result": "numeric_difference" if same else "formula_difference",
                          "detail": "문서의 획수로 계산하면 같음 — 획수 기준 차이" if same
                          else "문서 획수로도 재현되지 않음 — 격 계산 공식(외자·복성 처리 등) 차이"})
        else:
            items.append({"item": "원형이정 4격", "doc": doc_gyeok, "result": "formula_difference",
                          "detail": "원획·필획, 가수 유무 4가지 조합 모두 재현되지 않음"})
    elif doc_gyeok:
        items.append({"item": "원형이정 4격", "doc": doc_gyeok, "result": "not_comparable",
                      "detail": "이름 한글·한자가 검토된 값으로 필요"})

    # 3) 81수리 길흉 — 문서의 수로 우리 표를 조회
    for k in GYEOK_KO:
        label = v.get(f"luck.{k}")
        if not label:
            continue
        n = doc_gyeok.get(k)
        if n is None:
            items.append({"item": f"{GYEOK_KO[k]} 길흉", "doc": label, "result": "not_comparable", "detail": "격 수가 없음"})
            continue
        ours_l = luck_of(n)
        alts = {a["class"] for a in ours_l.get("alternatives", [])}
        res = "match" if ours_l["class"] == label else ("source_difference")
        items.append({"item": f"{GYEOK_KO[k]} 길흉({n})", "doc": LUCK_KO.get(label, label), "ours": ours_l["label"],
                      "result": res,
                      "detail": ("통용 분류와 일치" if res == "match" else
                                 "학파 이견이 있는 수 — 대안 분류와 일치" if label in alts else
                                 "81수리 분류표 출처·학파 차이(전통 해석 · 출처 대조 전)")})

    # 4) 사주 명식 — 출생정보(문서 또는 프로젝트) + 옵션 조합으로 재현 탐색
    pillars = v.get("saju_pillars")
    if pillars:
        bdate = v.get("birth_date") or (birth_profile.date if birth_profile else None)
        btime = v.get("birth_time") or (birth_profile.time if birth_profile else None)
        cal = v.get("birth_calendar") or (birth_profile.calendar if birth_profile else "solar")
        if not bdate:
            items.append({"item": "사주 명식", "doc": pillars, "result": "not_comparable", "detail": "출생일 정보 없음"})
        else:
            items.append(_saju_item(pillars, bdate, btime, cal))

    summary = {k: sum(1 for i in items if i["result"] == k)
               for k in ("match", "numeric_difference", "formula_difference", "source_difference", "not_comparable")}
    summary["note"] = "해석의 참/거짓 판정이 아니라, 선택된 공식·입력 기준으로 재현되는지 확인한 결과입니다."
    res = CrosscheckResult(document_id=doc.id, summary=summary, items=items,
                           engine_versions={"calendar": ENGINE_VERSION, "numerology_rule": RULE_VERSION})
    session.add(res)
    session.flush()
    return res


def _saju_item(pillars: str, bdate: str, btime: str | None, cal: str) -> dict:
    try:
        d = date.fromisoformat(bdate)
        t = time.fromisoformat(btime) if btime else None
    except ValueError:
        return {"item": "사주 명식", "doc": pillars, "result": "not_comparable", "detail": "출생일시 형식 오류"}
    doc_p = pillars.split()
    combos = [("off", None), ("longitude_only", SEOUL_LON), ("with_equation_of_time", SEOUL_LON)]
    reproduced, tried = [], []
    for (tst, lon), zi in itertools.product(combos, ("jojasi_next_day", "yajasi_same_day")):
        try:
            r = calculate(BirthInput(cal, d, False, t, None), SajuOptions(tst, zi, lon))
        except (CalendarInputError, OutOfSupportedRange) as e:
            return {"item": "사주 명식", "doc": pillars, "result": "not_comparable", "detail": e.message}
        segs = r["segments"]
        texts = {s["text"] for s in segs}
        ok = (" ".join(doc_p) in texts) if t else any(s["text"].split()[:3] == doc_p[:3] for s in segs)
        tried.append({"true_solar_time": tst, "zi_convention": zi, "ours": sorted(texts)[:3]})
        if ok:
            reproduced.append({"true_solar_time": tst, "zi_convention": zi})
    if reproduced:
        return {"item": "사주 명식", "doc": pillars, "result": "match", "reproduced_by": reproduced,
                "detail": "재현되는 시각 기준·자시 옵션: " + ", ".join(f"{r['true_solar_time']}/{r['zi_convention']}" for r in reproduced)}
    ours0 = tried[0]["ours"][0].split() if tried and tried[0]["ours"] else []
    diff = [n for n, a, b in zip(("연주", "월주", "일주", "시주"), doc_p, ours0) if a != b]
    return {"item": "사주 명식", "doc": pillars, "ours": tried[0]["ours"] if tried else None,
            "result": "numeric_difference" if diff and set(diff) <= {"시주"} else "formula_difference",
            "detail": f"다른 기둥: {', '.join(diff) or '알 수 없음'} — 출생 시각·지역·달력(음/양력) 또는 만세력 기준 차이 가능",
            "tried": tried}
