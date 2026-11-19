"""FastAPI 앱 팩토리. 실행: `python scripts/tasks.py dev-api` (uvicorn --factory, 127.0.0.1:8000)."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import namecraft
from namecraft import logging_safe
from namecraft.auth import ensure_token
from namecraft.config import Settings, get_settings
from namecraft.errors import AppError
from namecraft_api.deps import require_local_auth
from namecraft_api.middleware import SecurityAndAccessLogMiddleware
from namecraft_api.routers import ai, collab, health, imports, lexicon, names, numerology, projects, reports, saju

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging_safe.install()

    app = FastAPI(title="NameCraft AI API", version=namecraft.__version__, openapi_url=f"{API_PREFIX}/openapi.json")
    app.state.settings = settings
    app.state.local_token = ensure_token(settings.resolved_token_file)

    app.add_middleware(SecurityAndAccessLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        # 입력값 원문(개인정보 가능)은 응답/로그에 되돌리지 않고 위치·유형만 반환
        details = [{"loc": e.get("loc"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"status": "error", "error": {
            "code": "validation_error", "message": "입력값이 올바르지 않습니다.", "details": {"errors": details}}})

    app.include_router(health.router, prefix=API_PREFIX)  # 인증 예외
    protected = [Depends(require_local_auth)]
    app.include_router(ai.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(lexicon.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(saju.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(numerology.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(names.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(projects.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(collab.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(imports.router, prefix=API_PREFIX, dependencies=protected)
    app.include_router(reports.router, prefix=API_PREFIX, dependencies=protected)

    @app.get(f"{API_PREFIX}/auth/whoami", dependencies=protected, tags=["auth"])
    def whoami():
        return {"status": "ok", "data": {"mode": "local_single_user"}}

    return app

