"""Phase 12 보안 점검 (기획서 §22.1 보안: 권한 우회 · 업로드 · LLM 출력 주입 · 개인정보 로그 누출)."""

from __future__ import annotations

import io
import logging
import re

import pytest

pytestmark = pytest.mark.security

PUBLIC = {("GET", "/api/v1/health")}


def _routes(app):
    """OpenAPI 스키마 기준 전체 라우트(포함된 라우터의 접두어가 반영된 전체 경로)."""
    for path, ops in app.openapi()["paths"].items():
        for m in ops:
            if m in ("get", "post", "put", "patch", "delete"):
                yield m.upper(), path


def test_every_api_route_requires_token_except_health(client):
    """권한 우회: 새 라우트를 추가하고 인증을 빠뜨리면 이 테스트가 실패한다."""
    unprotected = []
    for method, path in _routes(client.app):
        if (method, path) in PUBLIC:
            continue
        url = re.sub(r"\{[^}]+\}", "x", path)
        r = client.request(method, url, json={})
        if r.status_code != 401:
            unprotected.append((method, path, r.status_code))
    assert unprotected == []
    assert len(list(_routes(client.app))) > 60  # 라우트 목록이 실제로 수집됐는지


def test_wrong_scheme_and_token_rejected(client):
    for h in ({"Authorization": client.token}, {"Authorization": "Basic " + client.token},
              {"Authorization": "Bearer " + client.token[:-1] + "x"}):
        assert client.get("/api/v1/projects", headers=h).status_code == 401


def test_security_headers_and_no_store(client, auth):
    r = client.get("/api/v1/projects", headers=auth)
    for k in ("x-content-type-options", "x-frame-options", "referrer-policy"):
        assert k in r.headers
    assert r.headers["cache-control"] == "no-store"


def test_cors_rejects_foreign_origin(client, auth):
    r = client.options("/api/v1/projects", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None


def test_access_log_has_route_template_not_personal_data(lexicon_client, caplog):
    with caplog.at_level(logging.INFO, logger="namecraft.access"):
        lexicon_client.get("/api/v1/surnames", params={"q": "심"})
        p = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "심"}).json()["data"]
        lexicon_client.get(f"/api/v1/projects/{p['id']}")
        lexicon_client.post("/api/v1/saju/calculate", json={"date": "2027-01-15", "time": "10:30"})
    text = caplog.text
    assert "GET /api/v1/surnames 200" in text and "/api/v1/projects/{project_id}" in text
    for leaked in ("심", p["id"], "2027-01-15", "10:30", "q="):
        assert leaked not in text


def test_whole_flow_logs_no_birth_or_name_data(lexicon_client, caplog):
    with caplog.at_level(logging.DEBUG):
        p = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "심", "surname_hanja": "沈"}).json()["data"]
        lexicon_client.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={"date": "2027-01-15", "time": "09:40"})
        lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "지아", "given_hanja": "智雅"})
        lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates")
    for leaked in ("지아", "智雅", "2027-01-15", "09:40"):
        assert leaked not in caplog.text


def test_ai_reason_html_is_stored_as_plain_text_only(lexicon_session):
    """LLM 출력 주입: AI 설명은 문자열 데이터로만 다룬다(화면은 React 가 이스케이프). 길이 제한 유지."""
    from namecraft.services import ai_generation as aig
    from namecraft.services.generation import GenerateRequest

    doc = {"candidates": [{"given_hangul": "하린", "reason": "<img src=x onerror=alert(1)>" + "가" * 400}]}
    a = aig.validate_candidates(lexicon_session, doc, GenerateRequest(surname_hangul="심", name_type="any"))["accepted"][0]
    assert a["reason"].startswith("<img") and len(a["reason"]) == 300  # 실행되지 않는 텍스트, 300자 제한
    with pytest.raises(Exception):
        aig.parse_ai_json('{"candidates": [{"given_hangul": "하린", "official_status": "verified"}]}')  # 판정 필드 주입 차단


def test_upload_html_disguised_as_text_is_served_as_plain_text(lexicon_client):
    d = lexicon_client.post("/api/v1/imports", files={"file": ("x.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html")}).json()["data"]
    f = lexicon_client.get(f"/api/v1/imports/{d['id']}/file")
    assert f.headers["content-type"].startswith("text/plain")  # HTML 로 해석되지 않음
    assert f.headers["x-content-type-options"] == "nosniff" and "default-src 'none'" in f.headers["content-security-policy"]


def test_token_file_not_world_readable_where_supported(settings):
    import os
    import stat

    from namecraft.auth import ensure_token

    ensure_token(settings.resolved_token_file)
    if os.name != "nt":  # Windows ACL 은 별도
        assert stat.S_IMODE(settings.resolved_token_file.stat().st_mode) == 0o600


@pytest.mark.perf
def test_performance_budget_generation_and_ranking(lexicon_client):
    """성능 회귀 방지(테스트 DB 기준 넉넉한 예산). 실측은 scripts/perf.py 와 docs/PERFORMANCE.md."""
    import time

    p = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "심", "surname_hanja": "沈",
                                                      "preferences": {"name_type": "any", "count": 30}}).json()["data"]
    t = time.perf_counter()
    g = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "none"})
    gen = time.perf_counter() - t
    t = time.perf_counter()
    lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates")
    rank = time.perf_counter() - t
    assert g.status_code == 200 and gen < 5.0 and rank < 3.0, (gen, rank)
