"""Phase 2 게이트: 이체자·독음·획수 출처 검증, 데이터 버전·체크섬, 멱등성."""

from __future__ import annotations

from sqlalchemy import func, select

from namecraft.adapters.importers.scourt_hanja import ImportFormatError, import_official_csv
from namecraft.adapters.importers.unihan import import_unihan, parse_unihan_zip
from namecraft.db.models import (
    DataReleaseVersion, HanjaCharacter, HanjaReading, HanjaStrokeCount, HanjaVariant,
    OfficialNameCharacterRule, ReferenceSource, Surname,
)

from conftest import SCOURT_SAMPLE, UNIHAN_FIXTURE


def test_parse_reads_version_and_korean_subset():
    version, entries = parse_unihan_zip(UNIHAN_FIXTURE.read_bytes())
    assert version == "18.0.0"
    assert entries["U+6C88"].readings == [("심", "0N"), ("침", "0E")]


def test_every_record_has_source_and_unverified_status(lexicon_session):
    s = lexicon_session
    assert s.scalar(select(func.count()).select_from(HanjaCharacter)) > 100
    for model, col in ((HanjaCharacter, HanjaCharacter.record_status), (HanjaReading, HanjaReading.status),
                       (HanjaStrokeCount, HanjaStrokeCount.status)):
        statuses = set(s.scalars(select(col).distinct()))
        assert statuses <= {"unverified", "conflict"}, model  # Unihan은 절대 verified 아님
    assert set(s.scalars(select(HanjaReading.source_id).distinct())) == {"SRC-UNIHAN"}


def test_compat_character_kept_distinct_with_canonical_link(lexicon_session):
    li_compat = lexicon_session.get(HanjaCharacter, "U+F9E1")
    assert li_compat.is_compatibility and li_compat.canonical_codepoint == "U+674E"
    readings = set(lexicon_session.scalars(select(HanjaReading.reading).where(HanjaReading.codepoint == "U+F9E1")))
    assert readings == {"이"}
    v = lexicon_session.scalars(select(HanjaVariant).where(HanjaVariant.codepoint == "U+F9E1")).one()
    assert (v.variant_codepoint, v.variant_type) == ("U+674E", "compatibility")


def test_multi_reading_with_name_flags(lexicon_session):
    rows = {r.reading: r for r in lexicon_session.scalars(select(HanjaReading).where(HanjaReading.codepoint == "U+6A02"))}
    assert set(rows) == {"낙", "락", "악", "요"}
    assert rows["악"].is_name_reading and rows["락"].is_name_reading  # N / E 플래그
    assert rows["낙"].is_name_reading is False  # 플래그 0 만 있음


def test_modern_and_original_strokes_stored_separately(lexicon_session):
    s = lexicon_session
    rows = {r.system: r for r in s.scalars(select(HanjaStrokeCount).where(HanjaStrokeCount.codepoint == "U+6C88"))}
    assert (rows["modern"].strokes, rows["modern"].rule_id) == (7, "STROKE.MODERN.UNIHAN.v1")
    assert (rows["original"].strokes, rows["original"].rule_id) == (8, "STROKE.ORIGINAL.v1")
    assert rows["original"].profile_id == "kr-common-2026" and rows["original"].status == "unverified"


def test_release_recorded_with_checksum(lexicon_session):
    rel = [r for r in lexicon_session.scalars(select(DataReleaseVersion)) if r.id.startswith("unihan-18.0.0-")]
    assert len(rel) == 1 and rel[0].is_sample is True
    assert len(rel[0].checksums["unihan-subset.zip"]) == 64


def test_import_is_idempotent(lexicon_session):
    before = lexicon_session.scalar(select(func.count()).select_from(HanjaReading))
    import_unihan(lexicon_session, UNIHAN_FIXTURE, is_sample=True)
    assert lexicon_session.scalar(select(func.count()).select_from(HanjaReading)) == before


def test_manifests_synced_including_user_input(lexicon_session):
    ids = set(lexicon_session.scalars(select(ReferenceSource.id)))
    assert {"SRC-UNIHAN", "SRC-SCOURT-HANJA", "SRC-DEV-SURNAME-SEED", "SRC-USER-INPUT"} <= ids


def test_surname_seed_cross_checked_against_unihan(lexicon_session):
    s = lexicon_session
    shim = s.scalars(select(Surname).where(Surname.hanja == "沈")).one()
    assert shim.record_status == "unverified" and shim.note is None
    namgung = s.scalars(select(Surname).where(Surname.hanja == "南宮")).one()
    assert namgung.is_compound and namgung.hanja_codepoints == ["U+5357", "U+5BAE"]
    # 시드 전체가 Unihan 독음과 맞아야 함 — 충돌 목록을 그대로 보여 주어 디버깅 가능하게
    conflicts = [(x.hangul, x.hanja, x.note) for x in s.scalars(select(Surname).where(Surname.record_status == "conflict"))]
    assert conflicts == []


def test_sample_official_csv_never_counts_as_real(lexicon_session):
    stats = import_official_csv(lexicon_session, SCOURT_SAMPLE, is_sample=True)
    assert stats["rules"] == 3
    assert lexicon_session.scalar(select(func.count()).select_from(OfficialNameCharacterRule)
                                  .where(OfficialNameCharacterRule.is_sample.is_(False))) == 0


def test_official_csv_rejects_bad_format(lexicon_session, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("char,reading\n沈,심\n", encoding="utf-8")
    try:
        import_official_csv(lexicon_session, bad, is_sample=False)
    except ImportFormatError:
        pass
    else:
        raise AssertionError("format error expected")


def test_official_conflict_marks_character(lexicon_session, tmp_path):
    f = tmp_path / "official.csv"
    # 沈의 Unihan 인명용 힌트 독음은 {심(N), 침(E)}. 공식 자료가 다른 독음을 말하면 conflict.
    f.write_text("hanja,reading,effective_date,legal_basis\n沈,침,2024-01-01,TEST\n秀,탐,2024-01-01,TEST\n",
                 encoding="utf-8")
    stats = import_official_csv(lexicon_session, f, is_sample=False)
    assert stats["conflicts"] == 1
    assert lexicon_session.get(HanjaCharacter, "U+6C88").record_status == "unverified"
    assert lexicon_session.get(HanjaCharacter, "U+79C0").record_status == "conflict"
