from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from namecraft.config import REPO_ROOT, Settings
from namecraft.db import migrate


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(var_dir=tmp_path, database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")


@pytest.fixture
def migrated_settings(settings: Settings) -> Settings:
    migrate.upgrade(settings.resolved_database_url)
    return settings


@pytest.fixture
def client(migrated_settings: Settings) -> TestClient:
    from namecraft_api.main import create_app

    app = create_app(migrated_settings)
    c = TestClient(app)
    c.token = app.state.local_token  # type: ignore[attr-defined]
    return c


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.token}"}  # type: ignore[attr-defined]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
