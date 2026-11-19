"""모든 API 응답의 공통 필드(기획서 §18) 및 검증 상태 정의(§22.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class VerificationStatus(StrEnum):
    verified = "verified"
    calculated = "calculated"
    traditional_interpretation = "traditional_interpretation"
    subjective = "subjective"
    unverified = "unverified"
    not_applicable = "not_applicable"
    conflict = "conflict"
    mock = "mock"  # 개발용 mock/sample — 운영 결과로 취급 금지


class Warning_(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    """REQ-NF-001 공통 응답 필드."""

    status: str = "ok"
    data: T
    data_version: str
    rule_profile: str | None = None
    rule_version: str | None = None
    calculation_assumptions: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus | None = None
    warnings: list[Warning_] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def envelope(data: T, **kwargs: Any) -> Envelope[T]:
    from namecraft.config import get_settings

    kwargs.setdefault("data_version", get_settings().data_version)
    return Envelope[T](data=data, **kwargs)
