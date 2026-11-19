from __future__ import annotations

from fastapi import Header, Request

from namecraft.auth import verify_bearer


def require_local_auth(request: Request, authorization: str | None = Header(default=None)) -> None:
    verify_bearer(authorization, request.app.state.local_token)


def get_db(request: Request):
    from sqlalchemy.orm import sessionmaker

    from namecraft.db import get_engine

    factory = sessionmaker(bind=get_engine(request.app.state.settings.resolved_database_url), expire_on_commit=False)
    with factory() as session:
        yield session
