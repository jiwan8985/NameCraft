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


UNIHAN_FIXTURE = REPO_ROOT / "datasets" / "fixtures" / "unihan-subset.zip"
SCOURT_SAMPLE = REPO_ROOT / "datasets" / "fixtures" / "scourt-hanja.sample.csv"


@pytest.fixture
def db_session(migrated_settings: Settings):
    from sqlalchemy.orm import sessionmaker

    from namecraft.db import get_engine

    with sessionmaker(bind=get_engine(migrated_settings.resolved_database_url))() as s:
        yield s


@pytest.fixture
def lexicon_session(db_session):
    from namecraft.adapters.importers.sources import sync_manifests
    from namecraft.adapters.importers.surnames import import_surname_seed
    from namecraft.adapters.importers.unihan import import_unihan

    sync_manifests(db_session)
    import_unihan(db_session, UNIHAN_FIXTURE, is_sample=True)
    import_surname_seed(db_session)
    db_session.commit()
    return db_session


@pytest.fixture
def lexicon_client(migrated_settings: Settings, lexicon_session):
    from namecraft_api.main import create_app

    app = create_app(migrated_settings)
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {app.state.local_token}"
    return c
