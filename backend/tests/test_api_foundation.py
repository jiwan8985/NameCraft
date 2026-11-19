"""Phase 1 게이트: API 헬스체크, 공통 응답 필드, 로컬 인증, 구조화 오류."""

from __future__ import annotations

from sqlalchemy import inspect

from namecraft.db import get_engine, migrate

ENVELOPE_FIELDS = {
    "status", "data_version", "rule_profile", "rule_version", "calculation_assumptions",
    "verification_status", "warnings", "provenance", "generated_at",
}


def test_health_ok_with_migrated_db(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert ENVELOPE_FIELDS <= body.keys()  # REQ-NF-001
    assert body["status"] == "ok"
    assert body["data"]["db"] == {"ok": True, "revision": "0001"}
    assert body["warnings"] == []


def test_health_warns_when_not_migrated(settings):
    from fastapi.testclient import TestClient

    from namecraft_api.main import create_app

    body = TestClient(create_app(settings)).get("/api/v1/health").json()
    assert body["data"]["db"]["revision"] is None
    assert [w["code"] for w in body["warnings"]] == ["db_not_migrated"]


def test_protected_routes_require_token(client, auth):
    for path in ["/api/v1/ai/providers", "/api/v1/auth/whoami"]:
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
        assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get(path, headers=auth).status_code == 200


def test_token_persisted_and_reused(settings):
    from namecraft.auth import ensure_token

    a = ensure_token(settings.resolved_token_file)
    b = ensure_token(settings.resolved_token_file)
    assert a == b and len(a) >= 32


def test_not_found_is_structured(client, auth):
    r = client.post("/api/v1/ai/providers/openai_api/test", headers=auth)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_migration_roundtrip(settings):
    url = settings.resolved_database_url
    migrate.upgrade(url)
    tables = set(inspect(get_engine(url)).get_table_names())
    assert {"users", "audit_logs", "reference_sources", "data_release_versions"} <= tables
    migrate.downgrade(url)
    get_engine.cache_clear()
    assert set(inspect(get_engine(url)).get_table_names()) <= {"alembic_version"}
