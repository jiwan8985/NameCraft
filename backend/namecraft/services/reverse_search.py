"""이름 역검색·한자 조합 최적화·대체 한자 추천 (기획서 §8.2, §8.4, REQ-GEN-002/004/005).

흐름: 한글 이름 → 음절별 인명용 독음 한자 → 공식 허용 판정 → 조합별 획수·수리·뜻 주의 → 선호 기준 정렬.

판정 버킷 (§8.4)
  passed      — 모든 글자가 공식 인명용 한자표에서 확인됨
  on_hold     — 공식 자료 미적재/샘플뿐이라 판정 보류 (추천 통과와 구별)
  rejected    — 공식 자료상 미수록 글자 포함, 또는 하드 조건 위반
정렬 점수(optimization_score)는 '조합 고르기 보조' 용도이며 Phase 7 최종 랭킹과 별개다. 구성요소를 모두 공개한다.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import HanjaCharacter, HanjaReading
from namecraft.domain.numerology.core import JAWON_BY_RADICAL, four_gyeok, luck_of, yinyang
from namecraft.domain.onomastics.analysis import meaning_review
from namecraft.domain.text import codepoint, is_hangul_syllable, normalize_name_text
from namecraft.services.lexicon import (
    OFFICIAL_NOT_LISTED, OFFICIAL_VERIFIED, official_status, official_statuses, stroke_map, stroke_maps,
)

MAX_PER_SYLLABLE = 40
MAX_COMBINATIONS = 20000
DEFAULT_WEIGHTS = {"common_hanja": 0.35, "no_meaning_caution": 0.25, "luck81": 0.25, "yinyang_balance": 0.15}


class ReverseSearchError(ValueError):
    pass


@dataclass
class HanjaInfo:
    char: str
    codepoint: str
    reading: str
    original: int | None
    modern: int | None
    education: bool
    radical: int | None
    definition_en: str | None
    caution: list[str]
    official: str
    is_compat: bool

    @property
    def jawon(self) -> str | None:
        return JAWON_BY_RADICAL.get(self.radical) if self.radical else None

    def to_dict(self) -> dict:
        return {"char": self.char, "codepoint": self.codepoint, "reading": self.reading,
                "original_strokes": self.original, "modern_strokes": self.modern,
                "education_hanja": self.education, "definition_en": self.definition_en,
                "meaning_caution": self.caution, "official_status": self.official,
                "jawon": self.jawon, "is_compatibility": self.is_compat}


def _radical(rs: str | None) -> int | None:
    if not rs:
        return None
    head = rs.split()[0].split(".")[0]
    return int(head) if head.isdigit() else None


def candidates_for_syllable(session: Session, syllable: str, *, exclude_hanja: set[str] = frozenset(),
                            include_compat: bool = False, limit: int = MAX_PER_SYLLABLE,
                            cache: dict | None = None) -> list[HanjaInfo]:
    """cache: 한 요청 안에서만 쓰는 메모(요청 간 공유하지 않음 — 공식 자료 갱신 즉시 반영)."""
    key = (syllable, frozenset(exclude_hanja), include_compat)
    if cache is not None and key in cache:
        return cache[key][:limit]
    rows = [ch for ch in session.scalars(
        select(HanjaCharacter).join(HanjaReading, HanjaReading.codepoint == HanjaCharacter.codepoint)
        .where(HanjaReading.reading == syllable, HanjaReading.is_name_reading.is_(True))
        .distinct()).all()
        if ch.char not in exclude_hanja and (include_compat or not ch.is_compatibility)]
    cps = [ch.codepoint for ch in rows]
    strokes = stroke_maps(session, cps)
    official = official_statuses(session, cps, syllable)
    reviews = meaning_review([{"hanja": ch.char, "definition_en": ch.definition_en} for ch in rows])["characters"]
    out = []
    for ch, mr in zip(rows, reviews):
        st = strokes.get(ch.codepoint, {})
        out.append(HanjaInfo(ch.char, ch.codepoint, syllable, st.get("original"), st.get("modern"),
                             bool(ch.unihan_korean_education), _radical(ch.radical_stroke), ch.definition_en,
                             mr["caution_keywords"], official[ch.codepoint], ch.is_compatibility))
    # 교육용 한자 우선, 주의 키워드 없는 글자 우선, 획수 적당(≤ 20) 우선, 코드포인트로 안정 정렬
    out.sort(key=lambda h: (not h.education, bool(h.caution), (h.original or 99) > 20, h.codepoint))
    if cache is not None:
        cache[key] = out
    return out[:limit]


def _surname_strokes(session: Session, surname_hanja: str | None) -> list[int] | None:
    if not surname_hanja:
        return None
    vals = [stroke_map(session, codepoint(c)).get("original") for c in normalize_name_text(surname_hanja)]
    return None if None in vals else vals  # type: ignore[return-value]


def _bucket(chars: list[HanjaInfo]) -> str:
    statuses = {c.official for c in chars}
    if OFFICIAL_NOT_LISTED in statuses:
        return "rejected"
    if statuses == {OFFICIAL_VERIFIED}:
        return "passed"
    return "on_hold"


def score_combination(chars: list[HanjaInfo], surname_strokes: list[int] | None, weights: dict[str, float],
                      use_traditional: bool) -> dict[str, Any]:
    comps: dict[str, float | None] = {
        "common_hanja": sum(c.education for c in chars) / len(chars),
        "no_meaning_caution": 0.0 if any(c.caution for c in chars) else 1.0,
        "luck81": None, "yinyang_balance": None,
    }
    trad: dict[str, Any] = {}
    strokes = [c.original for c in chars]
    if use_traditional and surname_strokes and None not in strokes:
        gy = four_gyeok(surname_strokes, strokes)  # type: ignore[arg-type]
        lucks = {k: luck_of(v) for k, v in gy.items()}
        val = {"good": 1.0, "half": 0.5, "bad": 0.0}
        comps["luck81"] = sum(val[l["class"]] for l in lucks.values()) / 4
        yy = yinyang(surname_strokes + strokes)  # type: ignore[operator]
        comps["yinyang_balance"] = 1.0 if len(set(yy)) > 1 else 0.0
        trad = {"four_gyeok": gy, "luck81": {k: l["label"] for k, l in lucks.items()},
                "disputed": [k for k, l in lucks.items() if l["disputed"]], "yinyang": yy,
                "status": "source_check_pending"}
    used = {k: w for k, w in weights.items() if comps.get(k) is not None and w > 0}
    total_w = sum(used.values())
    score = round(sum(comps[k] * w for k, w in used.items()) / total_w * 100, 1) if total_w else None  # type: ignore[operator]
    missing = [k for k, w in weights.items() if w > 0 and comps.get(k) is None]
    return {"optimization_score": score, "components": comps, "weights_used": used,
            "not_available": missing, "traditional": trad or None}


def reverse_search(session: Session, *, given_hangul: str, surname_hanja: str | None = None,
                   fixed: dict[int, str] | None = None, exclude_hanja: list[str] | None = None,
                   weights: dict[str, float] | None = None, use_traditional: bool = True,
                   include_compat: bool = False, limit: int = 30, max_per_syllable: int = MAX_PER_SYLLABLE,
                   cache: dict | None = None) -> dict[str, Any]:
    given = normalize_name_text(given_hangul)
    if not given or len(given) > 4 or not all(is_hangul_syllable(c) for c in given):
        raise ReverseSearchError("한글 이름(1~4자)이 필요합니다.")
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    if any(w < 0 for w in weights.values()):
        raise ReverseSearchError("가중치는 음수일 수 없습니다.")
    fixed = {int(k): normalize_name_text(v) for k, v in (fixed or {}).items()}
    excl = set(exclude_hanja or [])

    per_syllable: list[list[HanjaInfo]] = []
    for i, syl in enumerate(given):
        cands = candidates_for_syllable(session, syl, exclude_hanja=excl, include_compat=include_compat,
                                        limit=max_per_syllable, cache=cache)
        if i in fixed:
            cands = [c for c in cands if c.char == fixed[i]] or _fixed_lookup(session, fixed[i], syl)
        per_syllable.append(cands)

    impossible = [given[i] for i, c in enumerate(per_syllable) if not c]
    syllable_info = [{"syllable": given[i], "candidate_count": len(c), "candidates": [h.to_dict() for h in c]}
                     for i, c in enumerate(per_syllable)]
    if impossible:
        return {"given_hangul": given, "syllables": syllable_info, "combinations": {"passed": [], "on_hold": [], "rejected": []},
                "impossible_syllables": impossible, "total_combinations": 0, "hangul_only_possible": True}

    s_strokes = _surname_strokes(session, surname_hanja)
    buckets: dict[str, list] = {"passed": [], "on_hold": [], "rejected": []}
    total = 0
    for combo in itertools.islice(itertools.product(*per_syllable), MAX_COMBINATIONS):
        total += 1
        chars = list(combo)
        s = score_combination(chars, s_strokes, weights, use_traditional)
        bucket = _bucket(chars)
        buckets[bucket].append({"hanja": "".join(c.char for c in chars), "chars": [c.char for c in chars],
                                "bucket": bucket, **s})
    for b in buckets.values():
        b.sort(key=lambda x: (-(x["optimization_score"] or 0), x["hanja"]))
    truncated = {k: len(v) > limit for k, v in buckets.items()}
    return {
        "given_hangul": given, "syllables": syllable_info,
        "combinations": {k: v[:limit] for k, v in buckets.items()},
        "counts": {k: len(v) for k, v in buckets.items()}, "truncated": truncated,
        "total_combinations": total, "impossible_syllables": [],
        "surname_strokes": s_strokes, "weights": weights, "use_traditional": use_traditional,
    }


def _fixed_lookup(session: Session, char: str, syllable: str) -> list[HanjaInfo]:
    """돌림자로 지정된 한자가 인명용 힌트 독음 목록에 없을 때: 독음 일치 여부만 확인해 포함."""
    ch = session.get(HanjaCharacter, codepoint(char))
    if ch is None:
        return []
    readings = set(session.scalars(select(HanjaReading.reading).where(HanjaReading.codepoint == ch.codepoint)))
    if syllable not in readings:
        return []
    st = stroke_map(session, ch.codepoint)
    return [HanjaInfo(ch.char, ch.codepoint, syllable, st.get("original"), st.get("modern"),
                      bool(ch.unihan_korean_education), _radical(ch.radical_stroke), ch.definition_en, [],
                      official_status(session, ch.codepoint, syllable)["status"], ch.is_compatibility)]


def alternative_hanja(session: Session, *, given_hangul: str, given_hanja: str, surname_hanja: str | None = None,
                      use_traditional: bool = True, per_position: int = 5) -> dict[str, Any]:
    """REQ-GEN-005: 현재 한자 조합의 글자를 하나씩 바꿔 개선되는 대안을 제시."""
    given = normalize_name_text(given_hangul)
    cur = normalize_name_text(given_hanja)
    if len(cur) != len(given):
        raise ReverseSearchError("한자와 한글의 글자 수가 같아야 합니다.")
    s_strokes = _surname_strokes(session, surname_hanja)
    per = [candidates_for_syllable(session, syl) for syl in given]
    current = []
    for i, ch in enumerate(cur):
        found = next((h for h in per[i] if h.char == ch), None) or (_fixed_lookup(session, ch, given[i]) or [None])[0]
        if found is None:
            raise ReverseSearchError(f"'{ch}'은(는) '{given[i]}' 독음의 한자로 확인되지 않습니다.")
        current.append(found)
    base = score_combination(current, s_strokes, DEFAULT_WEIGHTS, use_traditional)
    reasons = []
    for i, h in enumerate(current):
        r = []
        if h.caution:
            r.append(f"뜻 주의 키워드: {', '.join(h.caution)}")
        if h.official == OFFICIAL_NOT_LISTED:
            r.append("공식 인명용 한자표 미수록")
        if not h.education:
            r.append("교육용 기초한자 아님(낯선 글자일 수 있음)")
        reasons.append(r)
    positions = []
    for i in range(len(cur)):
        alts = []
        for h in per[i]:
            if h.char == cur[i]:
                continue
            trial = current[:i] + [h] + current[i + 1:]
            s = score_combination(trial, s_strokes, DEFAULT_WEIGHTS, use_traditional)
            if (s["optimization_score"] or 0) > (base["optimization_score"] or 0):
                alts.append({"replace_with": h.to_dict(), "hanja": "".join(c.char for c in trial),
                             "bucket": _bucket(trial), **s})
        alts.sort(key=lambda x: (-(x["optimization_score"] or 0), x["hanja"]))
        positions.append({"position": i, "current": current[i].to_dict(), "concerns": reasons[i],
                          "alternatives": alts[:per_position]})
    return {"given_hangul": given, "current_hanja": cur, "current": {**base, "bucket": _bucket(current)},
            "positions": positions}
