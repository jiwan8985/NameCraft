"""이름 수리 분석 서비스: DB의 한자 데이터로 CharInput 을 만들어 도메인 분석 호출."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from namecraft.db.models import HanjaCharacter
from namecraft.domain.numerology.core import JAWON_BY_RADICAL, CharInput, NumerologyOptions, analyze
from namecraft.domain.numerology.strokes import NUMERALS, original_strokes
from namecraft.domain.text import codepoint, is_hangul_syllable, is_hanja, normalize_name_text
from namecraft.services.lexicon import stroke_map


class NameInputError(ValueError):
    pass


def _radical(row: HanjaCharacter | None) -> int | None:
    if row is None or not row.radical_stroke:
        return None
    value = row.radical_stroke.split()[0].split(".")[0]
    return int(value) if value.isdigit() else None


def given_name_elements(session: Session, hanja: str | None) -> list[str | None]:
    """이름 한자의 부수 오행. 성씨 한자나 획수와 독립적으로 계산한다."""
    return [
        JAWON_BY_RADICAL.get(_radical(session.get(HanjaCharacter, codepoint(char))) or 0)
        for char in normalize_name_text(hanja or "")
    ]


def _chars(session: Session, hangul: str, hanja: str | None, opts: NumerologyOptions) -> list[CharInput]:
    hangul = normalize_name_text(hangul)
    hanja = normalize_name_text(hanja) if hanja else None
    if not hangul or not all(is_hangul_syllable(c) for c in hangul):
        raise NameInputError("한글 표기가 올바르지 않습니다.")
    if hanja is not None and (len(hanja) != len(hangul) or not all(is_hanja(c) for c in hanja)):
        raise NameInputError("한자 표기는 한글과 글자 수가 같아야 합니다.")
    out = []
    for i, h in enumerate(hangul):
        if hanja is None:
            out.append(CharInput(hangul=h))
            continue
        ch = hanja[i]
        cp = codepoint(ch)
        row = session.get(HanjaCharacter, cp)
        st = stroke_map(session, cp)
        notes = []
        orig = st.get("original")
        if opts.numeral_by_meaning and ch in NUMERALS:
            orig = NUMERALS[ch]
            notes.append("숫자 한자를 뜻으로 계산(numeral_by_meaning)")
        elif row is not None and orig is not None:
            o = original_strokes(ch, row.radical_stroke)
            if o.note:
                notes.append(o.note)
        if row is None:
            notes.append("한자 데이터 없음")
        radical = _radical(row)
        out.append(CharInput(hangul=h, hanja=ch, codepoint=cp, modern_strokes=st.get("modern"),
                             original_strokes=orig, radical=radical, stroke_status="unverified", notes=notes))
    return out


def analyze_name(session: Session, *, surname_hangul: str, surname_hanja: str | None, given_hangul: str,
                 given_hanja: str | None, opts: NumerologyOptions) -> dict[str, Any]:
    s = _chars(session, surname_hangul, surname_hanja, opts)
    g = _chars(session, given_hangul, given_hanja, opts)
    return analyze(s, g, opts)
