from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from namecraft.config import REPO_ROOT, Settings
from namecraft.db import migrate


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # ollama_url: 닫힌 포트 — 테스트가 실제 로컬 Ollama 에 접속하지 않도록
    return Settings(var_dir=tmp_path, database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
                    ollama_url="http://127.0.0.1:9")


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


# ---------------------------------------------------------------- AI 테스트 더블

import json as _json  # noqa: E402
import sys as _sys  # noqa: E402
import threading  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402


class FakeOllama:
    """로컬 Ollama HTTP API 흉내 (/api/version, /api/tags, /api/show, /api/chat)."""

    def __init__(self, models, chat_content='{"candidates": []}'):
        self.models, self.chat_content, self.requests = models, chat_content, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, obj, code=200):
                body = _json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/version":
                    self._send({"version": "0.0-fake"})
                elif self.path == "/api/tags":
                    self._send({"models": [{"name": m["name"], "size": m.get("size"), "details": {"family": m.get("family", "llama")}}
                                           for m in fake.models]})
                else:
                    self._send({}, 404)

            def do_POST(self):
                body = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append((self.path, body))
                if self.path == "/api/show":
                    m = next(m for m in fake.models if m["name"] == body["model"])
                    self._send({"capabilities": m["caps"]})
                elif self.path == "/api/chat":
                    self._send({"model": body["model"], "message": {"content": fake.chat_content},
                                "prompt_eval_count": 50, "eval_count": 80})
                else:
                    self._send({}, 404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def fake_ollama():
    servers = []

    def make(models, chat_content='{"candidates": []}'):
        f = FakeOllama(models, chat_content)
        servers.append(f)
        return f
    yield make
    for f in servers:
        f.close()


FAKE_CLI = """
import json, os, sys
log = os.environ.get("FAKE_CLI_LOG")
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Fake CLI)"); sys.exit(0)
prompt = sys.stdin.read()
if log:
    with open(log, "w", encoding="utf-8") as f:
        json.dump({"args": args, "env_keys": sorted(os.environ), "cwd_files": os.listdir("."),
                   "prompt": prompt}, f, ensure_ascii=False)
mode = os.environ.get("FAKE_CLI_MODE", "ok")
if mode == "ratelimit":
    sys.stderr.write("Error: usage limit reached"); sys.exit(1)
result = os.environ.get("FAKE_CLI_RESULT", '{"candidates": [{"given_hangul": "\uc9c0\uc6b0", "reason": "ok"}]}')
print(json.dumps({"type": "result", "result": result, "usage": {"input_tokens": 11, "output_tokens": 22},
                  "total_cost_usd": 0.5}))
"""


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    script = tmp_path / "fake_cli.py"
    script.write_text(FAKE_CLI, encoding="utf-8")
    log = tmp_path / "cli_log.json"
    monkeypatch.setenv("FAKE_CLI_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("GEMINI_API_KEY", "should-not-leak")
    return {"command": [_sys.executable, str(script)], "log": log}


@pytest.fixture(autouse=True)
def _no_wsl_autodetect(monkeypatch):
    """테스트는 이 PC 의 WSL 설치 여부와 무관해야 한다(자동 탐지 끔)."""
    from namecraft.ai_gateway import providers

    monkeypatch.setattr(providers, "wsl_lookup", lambda name: None)
