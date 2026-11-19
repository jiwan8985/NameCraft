"""성명학 원획 산출 규칙 — STROKE.ORIGINAL.v1 (trad).

원획 = 강희자전 부수의 **본래 획수** + 부수 외 나머지 획수.
Unihan `kRSUnicode` = "부수번호.나머지획수" 를 사용하므로, 변형 부수(氵·扌·忄·犭·礻·衤·月(肉)·艹·辶·阝·王·罒·耂)는
자동으로 본자(水4·手4·心4·犬4·示5·衣6·肉6·艸6·辵7·阜8/邑7·玉5·网6·老6) 획수로 환원된다.

- 부수 번호 뒤 작은따옴표(') 는 간체/변형 부수 표시 → 이 규칙을 적용하지 않고 `unknown` 처리.
- 숫자 한자(一~十)를 뜻으로 세는 학파 옵션 `numeral_by_meaning` (기본 off).
- 학파마다 다른 예외(예: 일부 학파의 특정 글자 별도 획수)는 profile 예외 표로 덮어쓴다(현재 비어 있음).
"""

from __future__ import annotations

from dataclasses import dataclass

RULE_ID = "STROKE.ORIGINAL.v1"

# 강희자전 214부수의 획수 구간 (부수 번호 범위 → 획수)
_RADICAL_STROKE_RANGES = [
    (1, 6, 1), (7, 29, 2), (30, 60, 3), (61, 94, 4), (95, 117, 5), (118, 146, 6), (147, 166, 7),
    (167, 175, 8), (176, 186, 9), (187, 194, 10), (195, 200, 11), (201, 204, 12), (205, 208, 13),
    (209, 210, 14), (211, 211, 15), (212, 213, 16), (214, 214, 17),
]
NUMERALS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# 화면 설명용: 대표 변형 부수 → 본자
ABBREVIATED_RADICALS = {
    85: ("氵", "水", 4), 64: ("扌", "手", 4), 61: ("忄", "心", 4), 94: ("犭", "犬", 4), 113: ("礻", "示", 5),
    145: ("衤", "衣", 6), 130: ("月", "肉", 6), 140: ("艹", "艸", 6), 162: ("辶", "辵", 7), 170: ("阝(좌)", "阜", 8),
    163: ("阝(우)", "邑", 7), 96: ("王", "玉", 5), 122: ("罒", "网", 6), 125: ("耂", "老", 6),
}


def radical_strokes(radical: int) -> int:
    for lo, hi, n in _RADICAL_STROKE_RANGES:
        if lo <= radical <= hi:
            return n
    raise ValueError(f"부수 번호 범위 밖: {radical}")


@dataclass(frozen=True)
class OriginalStrokes:
    strokes: int | None
    radical: int | None
    residual: int | None
    method: str  # radical_restoration | numeral_by_meaning | unknown
    note: str | None = None


def original_strokes(char: str, kRSUnicode: str | None, *, numeral_by_meaning: bool = False,
                     exceptions: dict[str, int] | None = None) -> OriginalStrokes:
    if exceptions and char in exceptions:
        return OriginalStrokes(exceptions[char], None, None, "profile_exception")
    if numeral_by_meaning and char in NUMERALS:
        return OriginalStrokes(NUMERALS[char], None, None, "numeral_by_meaning")
    if not kRSUnicode:
        return OriginalStrokes(None, None, None, "unknown", "부수 정보 없음")
    first = kRSUnicode.split()[0]  # 복수 값이면 첫째(주 부수)
    rad_s, _, res_s = first.partition(".")
    if "'" in rad_s or not res_s:
        return OriginalStrokes(None, None, None, "unknown", f"변형/간체 부수 표기({first}) — 규칙 미적용")
    radical, residual = int(rad_s), int(res_s)
    rs = radical_strokes(radical)
    note = None
    if radical in ABBREVIATED_RADICALS:
        short, full, n = ABBREVIATED_RADICALS[radical]
        note = f"부수 {full}({n}획) 기준 — 변형 {short} 사용 시 본자로 환원"
    return OriginalStrokes(rs + residual, radical, residual, "radical_restoration", note)
