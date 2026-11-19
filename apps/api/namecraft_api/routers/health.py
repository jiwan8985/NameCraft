from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

import namecraft
from namecraft.db import get_engine
from namecraft.provenance import Envelope, envelope

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Envelope[dict[str, Any]])
def health(request: Request) -> Envelope[dict[str, Any]]:
    db_state: dict[str, Any] = {"ok": False, "revision": None}
    try:
        with get_engine(request.app.state.settings.resolved_database_url).connect() as conn:
            conn.execute(text("SELECT 1"))
            db_state["ok"] = True
            try:
                db_state["revision"] = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:  # 마이그레이션 미적용
                db_state["revision"] = None
    except Exception as exc:  # pragma: no cover - 환경 의존
        db_state["error"] = type(exc).__name__

    warnings = []
    if db_state["ok"] and db_state["revision"] is None:
        warnings.append({"code": "db_not_migrated", "message": "DB 마이그레이션이 적용되지 않았습니다 (tasks.py migrate)."})
    return envelope(
        {"service": "namecraft-api", "version": namecraft.__version__, "db": db_state},
        status="ok" if db_state["ok"] else "degraded",
        warnings=warnings,
    )
