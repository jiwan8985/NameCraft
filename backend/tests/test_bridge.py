"""연결 브리지 (Claude Code·Antigravity 를 다른 위치·다른 PC 에서 사용) — 보안·동작 검사."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from namecraft.ai_gateway.providers import (
    AntigravityProvider, ClaudeCodeProvider, ProviderCallError, ProviderSettings,
)
from namecraft.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("namecraft_bridge", REPO_ROOT / "bridge" / "namecraft_bridge.py")
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)


@pytest.fixture
def bridge(fake_cli):
    b = nb.Bridge({"claude_code": fake_cli["command"], "antigravity": None}, token="T" * 40)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), nb.make_handler(b))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{srv.server_address[1]}", "token": "T" * 40, "log": fake_cli["log"]}
    srv.shutdown()


def _req(url, path, body=None, token=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url + path, data=data, method="POST" if data is not None else "GET",
                               headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_bridge_args_match_backend():
    for schema, model in ((None, None), ({"type": "object"}, "m1")):
        assert nb.claude_args(schema, model) == ClaudeCodeProvider().build_args(json_schema=schema, model_id=model)
        assert nb.agy_args(schema, model, 120) == AntigravityProvider().build_args(json_schema=schema, model_id=model)
    assert nb.FORBIDDEN_FLAGS == __import__("namecraft.ai_gateway.providers", fromlist=["x"]).FORBIDDEN_FLAGS


def test_bridge_requires_token(bridge):
    assert _req(bridge["url"], "/health")[0] == 401
    assert _req(bridge["url"], "/health", token="wrong")[0] == 401
    assert _req(bridge["url"], "/generate", {"provider": "claude_code", "system": "s", "prompt": "p"})[0] == 401
    assert not bridge["log"].exists()  # 인증 실패 시 CLI 실행 안 함


def test_bridge_health_and_generate(bridge):
    code, info = _req(bridge["url"], "/health", token=bridge["token"])
    assert code == 200 and info["providers"]["claude_code"]["found"] and not info["providers"]["antigravity"]["found"]
    code, r = _req(bridge["url"], "/generate", {"provider": "claude_code", "system": "SYS", "prompt": "P"}, token=bridge["token"])
    assert code == 200 and json.loads(r["text"])["candidates"][0]["given_hangul"] == "지우"
    assert r["tokens_in"] == 11 and "total_cost_usd" not in json.dumps(r)
    log = json.loads(bridge["log"].read_text(encoding="utf-8"))
    assert "ANTHROPIC_API_KEY" not in log["env_keys"] and log["cwd_files"] == [] and log["args"][:2] == ["-p", "--output-format"]


def test_bridge_rejects_unknown_provider_commands_and_big_bodies(bridge):
    t = bridge["token"]
    assert _req(bridge["url"], "/generate", {"provider": "bash", "system": "s", "prompt": "p"}, token=t) == (400, {"error": "unknown_provider"})
    # 요청으로 명령·옵션을 넘길 수 없음(무시됨) — 실행되는 것은 정해진 인자뿐
    code, _ = _req(bridge["url"], "/generate", {"provider": "claude_code", "system": "s", "prompt": "p",
                                                 "command": ["rm", "-rf", "/"], "args": ["--bare"]}, token=t)
    assert code == 200
    assert "--bare" not in json.loads(bridge["log"].read_text(encoding="utf-8"))["args"]
    assert _req(bridge["url"], "/generate", raw=b"x" * (nb.MAX_BODY + 1), token=t)[0] == 413
    assert _req(bridge["url"], "/generate", {"provider": "antigravity", "system": "s", "prompt": "p"}, token=t)[0] == 503


def test_backend_provider_via_bridge(bridge):
    ok = ClaudeCodeProvider(ProviderSettings(enabled=True, connection="bridge", bridge_url=bridge["url"], bridge_token=bridge["token"]))
    st = ok.status()
    assert st["state"] == "connected" and st["connection"] == "bridge" and st["version"].startswith("9.9.9")
    assert "bridge_token" not in st  # 토큰은 상태 응답에 넣지 않음
    res = ok.generate_text("P", system="S", json_schema=None, seed=None, model_id=None)
    assert "지우" in res.text and res.raw_meta["via"] == "bridge"
    bad = ClaudeCodeProvider(ProviderSettings(enabled=True, connection="bridge", bridge_url=bridge["url"], bridge_token="nope"))
    assert bad.status()["state"] == "auth_required"
    with pytest.raises(ProviderCallError) as e:
        bad.generate_text("P", system="S", json_schema=None, seed=None, model_id=None)
    assert e.value.kind == "auth_required"
    down = ClaudeCodeProvider(ProviderSettings(enabled=True, connection="bridge", bridge_url="http://127.0.0.1:9", bridge_token="x"))
    assert down.status()["state"] == "not_installed" and "브리지에 연결할 수 없습니다" in down.status()["message"]
    agy = AntigravityProvider(ProviderSettings(enabled=True, connection="bridge", bridge_url=bridge["url"], bridge_token=bridge["token"]))
    assert "그쪽 컴퓨터에" in agy.status()["message"]


def test_settings_api_bridge(lexicon_client, bridge):
    c = lexicon_client
    assert c.patch("/api/v1/ai/preferences", json={"provider_id": "claude_code", "bridge_url": "ftp://x"}).status_code == 400
    assert c.patch("/api/v1/ai/preferences", json={"provider_id": "ollama", "connection": "bridge"}).status_code == 400
    r = c.patch("/api/v1/ai/preferences", json={"provider_id": "claude_code", "connection": "bridge", "enabled": True,
                                                  "bridge_url": bridge["url"] + "/", "bridge_token": bridge["token"]}).json()["data"]
    assert r["bridge_url"] == bridge["url"] and r["bridge_token_set"] and "bridge_token" not in r
    prov = {p["provider_id"]: p for p in c.get("/api/v1/ai/providers").json()["data"]}
    assert prov["claude_code"]["execution_mode"] == "supported_cli_task" and bridge["token"] not in json.dumps(prov)
    t = c.post("/api/v1/ai/providers/claude_code/test?live=true").json()["data"]
    assert t["test_result"] == "ok" and t["test_names"] == ["지우"]
    # 실제 작명 흐름: 외부 전송 동의 후 브리지로 생성
    p = c.post("/api/v1/projects", json={"surname_hangul": "심", "preferences": {"name_type": "any", "count": 3}}).json()["data"]
    need = c.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "claude_code"})
    assert need.status_code == 400 and need.json()["error"]["details"]["consent_required"]
    g = c.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "claude_code", "consent": True}).json()["data"]
    assert g["provider_used"] == "claude_code" and [s["given_hangul"] for s in g["saved"]] == ["지우"]


def test_bridge_token_file(tmp_path):
    t1 = nb.load_token(tmp_path)
    assert nb.load_token(tmp_path) == t1 and len(t1) >= 40
    assert nb.load_token(tmp_path, rotate=True) != t1
    if sys.platform != "win32":
        assert (tmp_path / "token").stat().st_mode & 0o777 == 0o600
