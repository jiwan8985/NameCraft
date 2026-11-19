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
