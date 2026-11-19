"""이름 정밀 분석 (기획서 §18 POST /names/analyze): 언어 분석 + (한자 있으면) 수리 분석."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from namecraft.db.models import HanjaCharacter
from namecraft.domain.numerology.core import NumerologyOptions
from namecraft.domain.onomastics import analysis as la
from namecraft.domain.text import codepoint, is_hangul_syllable, is_hanja, normalize_name_text
from namecraft.services.numerology import NameInputError, analyze_name


def _validate(hangul: str, hanja: str | None) -> tuple[str, str | None]:
    hangul = normalize_name_text(hangul)
    hanja = normalize_name_text(hanja) if hanja else None
    if not hangul or not all(is_hangul_syllable(c) for c in hangul):
        raise NameInputError("한글 표기가 올바르지 않습니다.")
    if hanja is not None and (len(hanja) != len(hangul) or not all(is_hanja(c) for c in hanja)):
        raise NameInputError("한자 표기는 한글과 글자 수가 같아야 합니다.")
    return hangul, hanja


def analyze_full(session: Session, *, surname_hangul: str, surname_hanja: str | None, given_hangul: str,
                 given_hanja: str | None, numerology_options: NumerologyOptions | None = None) -> dict[str, Any]:
    s_h, s_x = _validate(surname_hangul, surname_hanja)
    g_h, g_x = _validate(given_hangul, given_hanja)
    full = s_h + g_h
    chars = []
    for ch in (g_x or ""):
        row = session.get(HanjaCharacter, codepoint(ch))
        chars.append({"hanja": ch, "definition_en": row.definition_en if row else None})

    result: dict[str, Any] = {
        "name": {"surname_hangul": s_h, "surname_hanja": s_x, "given_hangul": g_h, "given_hanja": g_x,
                 "full_hangul": full, "full_hanja": (s_x or "") + (g_x or "") if (s_x and g_x) else None},
        "phonetics": la.phonetic_features(full, len(s_h)),
        "caution": la.caution_candidates(full, len(s_h)),
        "meaning": la.meaning_review(chars) if g_x else {
            "status": "not_applicable", "note": "한자가 없는 이름 — 순우리말 어원은 출처가 확인된 경우에만 사실로 표시(현재 자료 없음)",
            "korean_meaning_status": "not_available"},
        "usability": la.usability_notes(full, len(s_h)),
        "romanization": la.romanize_name(s_h, g_h),
    }
    result["numerology"] = analyze_name(session, surname_hangul=s_h, surname_hanja=s_x, given_hangul=g_h,
                                        given_hanja=g_x, opts=numerology_options or NumerologyOptions())
    return result


def compare_similarity(names: list[dict]) -> list[dict]:
    """후보 목록의 쌍별 유사도 + 중복 표시 (Phase 6 다양성 제약에서 재사용)."""
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out.append({"a": i, "b": j, **la.similarity(names[i], names[j])})
    return out
