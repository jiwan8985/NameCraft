"""Phase 1 기반 테이블.

도메인 테이블(성씨·한자·이름·사주 등)은 각 Phase에서 마이그레이션으로 추가한다 (기획서 §16, §21.1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


Base.metadata.naming_convention = NAMING_CONVENTION


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(100))  # 표시용 별칭(실명 불필요)
    role: Mapped[str] = mapped_column(String(20), default="owner")  # owner | member | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """감사 로그 — 개인정보 원문 저장 금지. target은 ID만."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ReferenceSource(Base):
    """datasets/source-manifests 와 1:1 (DATA_SOURCES.md)."""

    __tablename__ = "reference_sources"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 예: SRC-SCOURT-HANJA
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority: Mapped[str] = mapped_column(String(50))
    license: Mapped[str | None] = mapped_column(String(200), nullable=True)
    license_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataReleaseVersion(Base):
    """데이터 스냅샷 버전 — 이전 보고서 재현용 (기획서 §16.2)."""

    __tablename__ = "data_release_versions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 예: 2026.11.0
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksums: Mapped[dict] = mapped_column(JSON, default=dict)
    is_sample: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# Phase 2: 성씨·한자·어휘 데이터 레이어 (기획서 §5, §16)
#
# 원칙
# - 출처(source_id)·검증상태(status)는 레코드/필드 단위로 분리 저장한다.
# - 법적 허용(official_name_character_rules)은 공식 출처만 기록한다. Unihan 등 비공식 힌트는
#   hanja_characters.unihan_korean_name 같은 별도 필드에만 둔다.
# - 현대 필획과 성명학 원획은 hanja_stroke_counts.system 으로 분리한다.
# ---------------------------------------------------------------------------

RECORD_STATUSES = ("verified", "unverified", "conflict", "deprecated")


class HanjaCharacter(Base):
    __tablename__ = "hanja_characters"

    codepoint: Mapped[str] = mapped_column(String(12), primary_key=True)  # "U+6C88"
    char: Mapped[str] = mapped_column(String(2))
    canonical_codepoint: Mapped[str] = mapped_column(String(12), index=True)  # 호환한자 → 통합한자
    is_compatibility: Mapped[bool] = mapped_column(default=False)
    radical_stroke: Mapped[str | None] = mapped_column(String(20), nullable=True)  # kRSUnicode
    definition_en: Mapped[str | None] = mapped_column(Text, nullable=True)  # kDefinition (참고용)
    unihan_korean_name: Mapped[str | None] = mapped_column(String(10), nullable=True)  # kKoreanName 판(비공식 힌트)
    unihan_korean_education: Mapped[str | None] = mapped_column(String(10), nullable=True)
    record_status: Mapped[str] = mapped_column(String(20), default="unverified")
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)


class HanjaReading(Base):
    __tablename__ = "hanja_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    reading: Mapped[str] = mapped_column(String(10), index=True)  # 한글 독음
    is_name_reading: Mapped[bool | None] = mapped_column(nullable=True)  # 출처가 말하는 인명용 여부 (None=정보 없음)
    flags: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 출처 원본 플래그(예: Unihan "0N")
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)


class HanjaVariant(Base):
    __tablename__ = "hanja_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    variant_codepoint: Mapped[str] = mapped_column(String(12))
    variant_type: Mapped[str] = mapped_column(String(30))  # compatibility|traditional|simplified|semantic|z
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))


class HanjaStrokeCount(Base):
    __tablename__ = "hanja_stroke_counts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    system: Mapped[str] = mapped_column(String(20))  # modern | original
    strokes: Mapped[int]
    rule_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # original 산출 규칙 (Phase 4)
    profile_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class HanjaElementMapping(Base):
    """자원오행 — 학파(profile)별, 출처 필수 (Phase 4에서 데이터 투입)."""

    __tablename__ = "hanja_element_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(ForeignKey("hanja_characters.codepoint", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(String(50))
    element: Mapped[str] = mapped_column(String(2))  # 木火土金水
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class OfficialNameCharacterRule(Base):
    """인명용 한자 법적 허용 — 공식 출처(SRC-SCOURT-HANJA 등) 레코드만."""

    __tablename__ = "official_name_character_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    codepoint: Mapped[str] = mapped_column(String(12), index=True)
    reading: Mapped[str] = mapped_column(String(10))  # 허용 독음
    allowed: Mapped[bool] = mapped_column(default=True)
    legal_basis: Mapped[str | None] = mapped_column(String(200), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 고시·시행일 YYYY-MM-DD
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_release_versions.id"), nullable=True)
    is_sample: Mapped[bool] = mapped_column(default=False)


class Surname(Base):
    __tablename__ = "surnames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hangul: Mapped[str] = mapped_column(String(10), index=True)
    hanja: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hanja_codepoints: Mapped[list] = mapped_column(JSON, default=list)
    is_compound: Mapped[bool] = mapped_column(default=False)
    record_status: Mapped[str] = mapped_column(String(20), default="unverified")
    is_provisional: Mapped[bool] = mapped_column(default=False)  # 사용자 입력 임시 레코드 (확정 보류)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SurnameVariant(Base):
    """두음법칙 등 대체 한글 표기 (예: 李 이/리, 柳 류/유)."""

    __tablename__ = "surname_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    surname_id: Mapped[str] = mapped_column(ForeignKey("surnames.id", ondelete="CASCADE"), index=True)
    hangul: Mapped[str] = mapped_column(String(10), index=True)
    variant_type: Mapped[str] = mapped_column(String(30), default="initial_sound_law")


class DictionaryTerm(Base):
    """어휘 의미·발음 (국립국어원 등, 라이선스 확인 후 투입 — Phase 5)."""

    __tablename__ = "dictionary_terms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    term: Mapped[str] = mapped_column(String(50), index=True)
    pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    pronunciation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hanja: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # 예: ["negative_association_candidate"]
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="unverified")


class NamePopularityDataset(Base):
    __tablename__ = "name_popularity_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("reference_sources.id"))
    year: Mapped[int]
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aggregation_basis: Mapped[str] = mapped_column(Text)  # 집계 기준
    coverage: Mapped[str] = mapped_column(String(100))  # 예: "top 10 only"
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NamePopularityRow(Base):
    __tablename__ = "name_popularity_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("name_popularity_datasets.id", ondelete="CASCADE"), index=True)
    name_hangul: Mapped[str] = mapped_column(String(20), index=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)
    count: Mapped[int | None] = mapped_column(nullable=True)
