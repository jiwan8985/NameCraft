from __future__ import annotations

from fastapi import Header, Request

from namecraft.auth import verify_bearer


def require_local_auth(request: Request, authorization: str | None = Header(default=None)) -> None:
    verify_bearer(authorization, request.app.state.local_token)
