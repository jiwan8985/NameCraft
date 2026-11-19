"""성씨·한자 조회 서비스 (기획서 §5, REQ-SN-001, REQ-HJ-001~005).

법적 허용 판정(official)과 비공식 힌트(Unihan)를 서로 다른 필드로 반환한다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from namecraft.adapters.importers.sources import USER_INPUT_SOURCE
from namecraft.db.models import (
    DataReleaseVersion,
    HanjaCharacter,
    HanjaReading,
    HanjaStrokeCount,
    HanjaVariant,
    OfficialNameCharacterRule,
    ReferenceSource,
    Surname,
    SurnameVariant,
)
from namecraft.domain.text import char_from_codepoint, codepoint, is_hangul_syllable, is_hanja, normalize_name_text

# ---------------------------------------------------------------- official status

OFFICIAL_VERIFIED = "verified"        # 공식 자료에 해당 글자(·독음) 수록
OFFICIAL_NOT_LISTED = "not_listed"    # 공식 자료가 적재되어 있으나 미수록 → 인명 사용 불가 가능성 (재확인 권장)
OFFICIAL_UNKNOWN = "unknown"          # 공식 자료 미적재 → 판정 불가
OFFICIAL_SAMPLE = "sample_only"       # 샘플 자료에만 존재 — 판정 근거 아님


def official_data_loaded(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(OfficialNameCharacterRule)
                               .where(OfficialNameCharacterRule.is_sample.is_(False))))


def official_status(session: Session, cp: str, reading: str | None = None) -> dict[str, Any]:
    rules = list(session.scalars(select(OfficialNameCharacterRule).where(OfficialNameCharacterRule.codepoint == cp)))
    real = [r for r in rules if not r.is_sample]
    if reading:
        real = [r for r in real if r.reading == reading]
    if real:
        status = OFFICIAL_VERIFIED
    elif official_data_loaded(session):
        status = OFFICIAL_NOT_LISTED
    elif any(r.is_sample for r in rules):
        status = OFFICIAL_SAMPLE
    else:
        status = OFFICIAL_UNKNOWN
    return {
        "status": status,
        "requires_official_recheck": status != OFFICIAL_VERIFIED,
        "allowed_readings": sorted({r.reading for r in rules if not r.is_sample}),
        "rules": [{"reading": r.reading, "legal_basis": r.legal_basis, "effective_date": r.effective_date,
                   "checked_at": r.checked_at.isoformat() if r.checked_at else None, "source_id": r.source_id,
                   "data_release_id": r.data_release_id, "is_sample": r.is_sample} for r in rules],
    }


# ---------------------------------------------------------------- hanja

def _detail(session: Session, ch: HanjaCharacter, readings, strokes, variants) -> dict[str, Any]:
    return {
        "codepoint": ch.codepoint,
        "char": ch.char,
        "canonical_codepoint": ch.canonical_codepoint,
        "is_compatibility": ch.is_compatibility,
        "record_status": ch.record_status,
        "radical_stroke": ch.radical_stroke,
        "definition_en": ch.definition_en,
        "definition_source": ch.source_id if ch.definition_en else None,
        "readings": [{"reading": r.reading, "is_name_reading": r.is_name_reading, "flags": r.flags,
                      "source_id": r.source_id, "status": r.status} for r in readings],
        "strokes": [{"system": s.system, "strokes": s.strokes, "rule_id": s.rule_id, "profile_id": s.profile_id,
                     "source_id": s.source_id, "status": s.status} for s in strokes],
        "variants": [{"codepoint": v.variant_codepoint, "char": char_from_codepoint(v.variant_codepoint),
                      "type": v.variant_type, "source_id": v.source_id} for v in variants],
        "hints": {"unihan_korean_name": ch.unihan_korean_name,
                  "unihan_korean_education": ch.unihan_korean_education},
        "official": official_status(session, ch.codepoint),
    }


def _load_details(session: Session, chars: list[HanjaCharacter]) -> list[dict[str, Any]]:
    cps = [c.codepoint for c in chars]
    by = lambda model: _group(session.scalars(select(model).where(model.codepoint.in_(cps))))  # noqa: E731
    readings, strokes, variants = by(HanjaReading), by(HanjaStrokeCount), by(HanjaVariant)
    return [_detail(session, c, readings[c.codepoint], strokes[c.codepoint], variants[c.codepoint]) for c in chars]


def _group(rows) -> dict[str, list]:
    out: dict[str, list] = defaultdict(list)
    for r in rows:
        out[r.codepoint].append(r)
    return out


def get_hanja(session: Session, cp: str) -> dict[str, Any] | None:
    ch = session.get(HanjaCharacter, "U+" + cp.upper().removeprefix("U+"))
    return _load_details(session, [ch])[0] if ch else None


def search_hanja(session: Session, *, char: str | None = None, reading: str | None = None,
                 name_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    q = select(HanjaCharacter)
    if char:
        char = normalize_name_text(char)
        if len(char) != 1 or not is_hanja(char):
            return []
        target = session.get(HanjaCharacter, codepoint(char))
        canonical = target.canonical_codepoint if target else codepoint(char)
        # 같은 통합 한자를 공유하는 호환 한자까지 함께 반환 (예: 李 U+674E ↔ U+F9E1)
        q = q.where(or_(HanjaCharacter.codepoint == canonical, HanjaCharacter.canonical_codepoint == canonical))
    if reading:
        reading = normalize_name_text(reading)
        if not all(is_hangul_syllable(c) for c in reading):
            return []
        rq = select(HanjaReading.codepoint).where(HanjaReading.reading == reading)
        if name_only:
            rq = rq.where(HanjaReading.is_name_reading.is_(True))
        q = q.where(HanjaCharacter.codepoint.in_(rq))
    q = q.order_by(HanjaCharacter.unihan_korean_education.is_(None), HanjaCharacter.codepoint).limit(limit)
    return _load_details(session, list(session.scalars(q)))


# ---------------------------------------------------------------- surnames

def _surname_dict(session: Session, s: Surname) -> dict[str, Any]:
    alts = list(session.scalars(select(SurnameVariant.hangul).where(SurnameVariant.surname_id == s.id)))
    chars = []
    for cp in s.hanja_codepoints:
        ch = session.get(HanjaCharacter, cp)
        st = stroke_map(session, cp)
        modern, original = st.get("modern"), st.get("original")
        chars.append({"codepoint": cp, "char": char_from_codepoint(cp), "in_hanja_db": ch is not None,
                      "modern_strokes": modern, "modern_strokes_status": "unverified" if modern else "not_available",
                      "original_strokes": original,
                      "original_strokes_status": "unverified" if original else "not_available"})
    return {"id": s.id, "hangul": s.hangul, "alt_hangul": alts, "hanja": s.hanja, "is_compound": s.is_compound,
            "record_status": s.record_status, "is_provisional": s.is_provisional, "source_id": s.source_id,
            "note": s.note, "characters": chars}


def stroke_map(session: Session, cp: str) -> dict[str, int]:
    return {s.system: s.strokes for s in session.scalars(select(HanjaStrokeCount).where(HanjaStrokeCount.codepoint == cp))}


def search_surnames(session: Session, q: str) -> list[dict[str, Any]]:
    q = normalize_name_text(q)
    if not q:
        return []
    variant_ids = select(SurnameVariant.surname_id).where(SurnameVariant.hangul == q)
    rows = session.scalars(select(Surname).where(or_(Surname.hangul == q, Surname.hanja == q,
                                                     Surname.id.in_(variant_ids)))
                           .order_by(Surname.is_provisional, Surname.hanja))
    return [_surname_dict(session, s) for s in rows]


def create_provisional_surname(session: Session, hangul: str, hanja: str | None) -> dict[str, Any]:
    hangul = normalize_name_text(hangul)
    hanja = normalize_name_text(hanja) if hanja else None
    if not hangul or not all(is_hangul_syllable(c) for c in hangul) or len(hangul) > 4:
        raise ValueError("hangul")
    if hanja and (len(hanja) != len(hangul) or not all(is_hanja(c) for c in hanja)):
        raise ValueError("hanja")
    s = Surname(hangul=hangul, hanja=hanja, hanja_codepoints=[codepoint(c) for c in hanja or ""],
                is_compound=len(hangul) > 1, record_status="unverified", is_provisional=True,
                source_id=USER_INPUT_SOURCE, note="사용자 입력 임시 레코드 — 확정 판정 보류")
    session.add(s)
    session.flush()
    return _surname_dict(session, s)


# ---------------------------------------------------------------- admin

def list_sources(session: Session) -> list[dict[str, Any]]:
    return [{"id": s.id, "name": s.name, "authority": s.authority, "url": s.url, "license": s.license,
             "license_verified_at": s.license_verified_at.isoformat() if s.license_verified_at else None,
             "status": s.status, "notes": s.notes}
            for s in session.scalars(select(ReferenceSource).order_by(ReferenceSource.id))]


def list_releases(session: Session) -> list[dict[str, Any]]:
    return [{"id": r.id, "description": r.description, "checksums": r.checksums, "is_sample": r.is_sample,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in session.scalars(select(DataReleaseVersion).order_by(DataReleaseVersion.created_at))]


def data_summary(session: Session) -> dict[str, Any]:
    count = lambda m, *w: session.scalar(select(func.count()).select_from(m).where(*w))  # noqa: E731
    return {
        "hanja_characters": count(HanjaCharacter),
        "hanja_by_status": dict(session.execute(select(HanjaCharacter.record_status, func.count())
                                                .group_by(HanjaCharacter.record_status)).all()),
        "hanja_readings": count(HanjaReading),
        "modern_stroke_counts": count(HanjaStrokeCount, HanjaStrokeCount.system == "modern"),
        "original_stroke_counts": count(HanjaStrokeCount, HanjaStrokeCount.system == "original"),
        "official_rules": count(OfficialNameCharacterRule, OfficialNameCharacterRule.is_sample.is_(False)),
        "official_rules_sample": count(OfficialNameCharacterRule, OfficialNameCharacterRule.is_sample.is_(True)),
        "surnames": count(Surname, Surname.is_provisional.is_(False)),
        "surnames_provisional": count(Surname, Surname.is_provisional.is_(True)),
        "surnames_conflict": count(Surname, Surname.record_status == "conflict"),
    }


def provenance_for(session: Session, source_ids: set[str]) -> list[dict[str, Any]]:
    rows = session.scalars(select(ReferenceSource).where(ReferenceSource.id.in_(source_ids)))
    return [{"source_id": s.id, "name": s.name, "authority": s.authority, "license": s.license,
             "status": s.status} for s in rows]
