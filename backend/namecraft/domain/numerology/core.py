"""수리성명학 계산 (기획서 §6.3, docs/ANALYSIS_RULES.md §4).

결과는 성격별로 분리한다:
- calc: 4격 수치, 81 환원, 수리오행, 음양 배열, 음령/자원 오행 '배정', 오행 관계
- trad: 81수리 길흉, 음양 조화 판단, 삼원오행, 자원오행(부수 규칙) — 모두 '출처 대조 전' 전통 해석
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from namecraft.config import REPO_ROOT
from namecraft.domain.hangul import initial_consonant
from namecraft.domain.numerology.elements import chain, digit_element

PROFILE_ID = "kr-common-2026"
RULE_VERSION = "0.1.0-draft"
TRAD_STATUS = "source_check_pending"  # 화면 표기: "전통 해석 · 출처 대조 전"
LUCK_KO = {"good": "길", "half": "반길", "bad": "흉"}

# NUM.EUMRYEONG.* — 초성 → 오행
EUMRYEONG = {
    "modern-common": {**dict.fromkeys("ㄱㅋ", "木"), **dict.fromkeys("ㄴㄷㄹㅌ", "火"), **dict.fromkeys("ㅇㅎ", "土"),
                      **dict.fromkeys("ㅅㅈㅊ", "金"), **dict.fromkeys("ㅁㅂㅍ", "水")},
    "hunmin-haerye": {**dict.fromkeys("ㄱㅋ", "木"), **dict.fromkeys("ㄴㄷㄹㅌ", "火"), **dict.fromkeys("ㅇㅎ", "水"),
                      **dict.fromkeys("ㅅㅈㅊ", "金"), **dict.fromkeys("ㅁㅂㅍ", "土")},
}
EUMRYEONG_LABEL = {"modern-common": "현대 통용", "hunmin-haerye": "훈민정음 해례본"}

# NUM.JAWON.RADICAL.v1 — 부수 의미가 오행과 직접 대응하는 경우만 배정, 나머지는 판정 보류(N/A)
JAWON_BY_RADICAL = {
    85: "水", 15: "水", 173: "水",                       # 水(氵), 冫, 雨
    75: "木", 140: "木", 118: "木", 115: "木",           # 木, 艸(艹), 竹, 禾
    86: "火",                                             # 火(灬)
    32: "土", 46: "土", 102: "土",                       # 土, 山, 田
    167: "金", 96: "金", 112: "金",                      # 金, 玉(王), 石
}


@dataclass(frozen=True)
class NumerologyOptions:
    stroke_system: str = "original"  # original | modern
    single_name_virtual_stroke: str = "none"  # none | plus_one
    eumryeong_school: str = "modern-common"
    numeral_by_meaning: bool = False

    def __post_init__(self):
        if self.stroke_system not in ("original", "modern"):
            raise ValueError("stroke_system")
        if self.single_name_virtual_stroke not in ("none", "plus_one"):
            raise ValueError("single_name_virtual_stroke")
        if self.eumryeong_school not in EUMRYEONG:
            raise ValueError("eumryeong_school")


# ---------------------------------------------------------------- calc

def four_gyeok(surname: list[int], given: list[int], *, virtual: str = "none") -> dict[str, int]:
    """NUM.WON/HYEONG/I/JEONG.v1 — 원형이정 4격. 복성은 합산(compound_surname_mode: sum)."""
    if not surname or not given:
        raise ValueError("성과 이름 획수가 모두 필요합니다.")
    s = sum(surname)
    if len(given) == 1:
        n1 = given[0]
        extra = 1 if virtual == "plus_one" else 0
        return {"won": n1 + extra, "hyeong": s + n1, "i": s + extra, "jeong": s + n1}
    return {"won": sum(given), "hyeong": s + given[0], "i": s + sum(given[1:]), "jeong": s + sum(given)}


def reduce81(n: int) -> int:
    """NUM.REDUCE81.v1 — 81 초과 시 80을 반복해서 뺀다."""
    while n > 81:
        n -= 80
    return n


def yinyang(strokes: list[int]) -> list[str]:
    """NUM.YINYANG.v1 — 홀수 양, 짝수 음."""
    return ["양" if n % 2 else "음" for n in strokes]


def eumryeong(hangul: str, school: str) -> list[str]:
    return [EUMRYEONG[school][initial_consonant(ch)] for ch in hangul]


def samwon(surname: list[int], given: list[int]) -> dict[str, int]:
    """NUM.SAMWON.KR-COMMON.v1 (trad 정의) — 천격=성+1(복성은 성 합), 인격=성+이름 첫자, 지격=이름 합(외자는 +1)."""
    s = sum(surname)
    return {"cheon": s + (1 if len(surname) == 1 else 0), "in": s + given[0],
            "ji": sum(given) + (1 if len(given) == 1 else 0)}


# ---------------------------------------------------------------- trad

@lru_cache(maxsize=4)
def luck_table(path: str = str(REPO_ROOT / "datasets" / "rules" / "luck81-kr-common.yaml")) -> dict[str, Any]:
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    assert set(doc["numbers"]) == set(range(1, 82)), "81수리 표는 1~81을 모두 포함해야 함"
    return doc


def luck_of(n: int) -> dict[str, Any]:
    t = luck_table()
    e = t["numbers"][reduce81(n)]
    out = {"number": n, "reduced": reduce81(n), "class": e["class"], "label": LUCK_KO[e["class"]],
           "disputed": bool(e.get("disputed")), "rule_id": t["rule_id"], "status": t["status"]}
    if e.get("disputed"):
        out["alternatives"] = [{"class": a, "label": LUCK_KO[a]} for a in e["alt"]]
    return out


def yinyang_judgement(pattern: list[str]) -> dict[str, str]:
    balanced = len(set(pattern)) > 1
    return {"value": "조화" if balanced else "편중",
            "basis": "한쪽(양 또는 음)으로만 이루어지면 편중으로 보는 통용 해석", "status": TRAD_STATUS}


# ---------------------------------------------------------------- analysis

@dataclass
class CharInput:
    hangul: str
    hanja: str | None = None
    codepoint: str | None = None
    modern_strokes: int | None = None
    original_strokes: int | None = None
    radical: int | None = None
    stroke_status: str = "unverified"
    notes: list[str] = field(default_factory=list)

    def strokes(self, system: str) -> int | None:
        return self.original_strokes if system == "original" else self.modern_strokes


def analyze(surname: list[CharInput], given: list[CharInput], opts: NumerologyOptions) -> dict[str, Any]:
    if not surname or not given:
        raise ValueError("성과 이름이 모두 필요합니다.")
    hangul_full = "".join(c.hangul for c in surname + given)
    warnings: list[dict] = []

    # 음령오행 — 한글 발음만 있으면 항상 적용 가능
    eum = {school: eumryeong(hangul_full, school) for school in EUMRYEONG}
    chosen = eum[opts.eumryeong_school]
    agree = [a == b for a, b in zip(eum["modern-common"], eum["hunmin-haerye"])]
    eumryeong_result = {
        "status": TRAD_STATUS, "school": opts.eumryeong_school,
        "elements": chosen, "relations": chain(chosen),
        "by_school": {s: {"label": EUMRYEONG_LABEL[s], "elements": v, "relations": chain(v)} for s, v in eum.items()},
        "school_agreement": {"agree_count": sum(agree), "total": len(agree),
                             "note": "학파 간 일치도는 정확성의 증거가 아닙니다."},
    }

    # 한자 기반 항목 — 한자가 하나라도 없으면 not_applicable (REQ-HJ-005)
    hanja_missing = [c.hangul for c in given if not c.hanja] + [c.hangul for c in surname if not c.hanja]
    if hanja_missing:
        return {
            "applicability": {"numerology": "not_applicable", "eumryeong": "applicable",
                              "reason": "한자가 지정되지 않은 글자가 있어 획수 기반 항목은 적용하지 않습니다."},
            "eumryeong": eumryeong_result, "warnings": warnings,
            "profile_id": PROFILE_ID, "rule_version": RULE_VERSION,
        }

    system = opts.stroke_system
    s_strokes = [c.strokes(system) for c in surname]
    g_strokes = [c.strokes(system) for c in given]
    if None in s_strokes + g_strokes:
        unknown = [c.hanja for c in surname + given if c.strokes(system) is None]
        return {
            "applicability": {"numerology": "unknown", "eumryeong": "applicable",
                              "reason": f"획수 정보를 확인할 수 없는 글자: {''.join(unknown)}"},
            "eumryeong": eumryeong_result, "warnings": [{"code": "stroke_unknown", "message": "획수 미확인 글자 포함"}],
            "profile_id": PROFILE_ID, "rule_version": RULE_VERSION,
        }
    if any(c.stroke_status != "verified" for c in surname + given):
        warnings.append({"code": "stroke_unverified", "message": "획수 자료가 공식 대조 전(unverified)입니다."})

    gy = four_gyeok(s_strokes, g_strokes, virtual=opts.single_name_virtual_stroke)  # type: ignore[arg-type]
    gyeok = {k: {"value": v, "reduced": reduce81(v), "element": digit_element(reduce81(v)), "luck": luck_of(v)}
             for k, v in gy.items()}
    yy = yinyang(s_strokes + g_strokes)  # type: ignore[arg-type]
    sw = samwon(s_strokes, g_strokes)  # type: ignore[arg-type]
    sw_el = [digit_element(sw[k]) for k in ("cheon", "in", "ji")]
    jawon = [JAWON_BY_RADICAL.get(c.radical) if c.radical else None for c in surname + given]
    luck_counts = {k: sum(1 for g in gyeok.values() if g["luck"]["class"] == k) for k in LUCK_KO}

    return {
        "applicability": {"numerology": "applicable", "eumryeong": "applicable"},
        "stroke_system": system,
        "characters": [{"hangul": c.hangul, "hanja": c.hanja, "codepoint": c.codepoint, "strokes": c.strokes(system),
                        "modern_strokes": c.modern_strokes, "original_strokes": c.original_strokes,
                        "stroke_status": c.stroke_status, "notes": c.notes} for c in surname + given],
        "calc": {
            "four_gyeok": {k: {"value": v["value"], "reduced": v["reduced"], "element": v["element"]}
                           for k, v in gyeok.items()},
            "yinyang_pattern": yy,
            "suri_element_relations": chain([gyeok[k]["element"] for k in ("won", "hyeong", "i", "jeong")]),
            "options": {"single_name_virtual_stroke": opts.single_name_virtual_stroke,
                        "compound_surname_mode": "sum", "numeral_by_meaning": opts.numeral_by_meaning},
        },
        "trad": {
            "status": TRAD_STATUS,
            "luck81": {k: v["luck"] for k, v in gyeok.items()},
            "luck81_counts": luck_counts,
            "yinyang": yinyang_judgement(yy),
            "samwon": {"values": sw, "elements": sw_el, "relations": chain(sw_el),
                       "rule_id": "NUM.SAMWON.KR-COMMON.v1", "status": TRAD_STATUS},
            "jawon": {"elements": jawon, "rule_id": "NUM.JAWON.RADICAL.v1", "status": TRAD_STATUS,
                      "note": "부수 의미가 오행과 직접 대응하는 글자만 배정, 나머지는 판정 보류(null)"},
        },
        "eumryeong": eumryeong_result,
        "warnings": warnings,
        "profile_id": PROFILE_ID,
        "rule_version": RULE_VERSION,
    }
