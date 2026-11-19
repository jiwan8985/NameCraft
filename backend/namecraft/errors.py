"""구조화된 오류 코드 (기획서 §18 '오류 코드는 구조화하여 반환')."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        return {"status": "error", "error": {"code": self.code, "message": self.message, "details": self.details}}


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class ProviderUnavailable(AppError):
    status_code = 503
    code = "provider_unavailable"
