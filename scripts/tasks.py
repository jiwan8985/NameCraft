"""NameCraft AI 로컬 작업 실행기 (make 대체, Windows/WSL/macOS 공용).

사용법:
    python scripts/tasks.py setup      # venv 의존성 + web npm 설치
    python scripts/tasks.py migrate    # DB 마이그레이션 (SQLite 기본)
    python scripts/tasks.py dev        # API(127.0.0.1:8000) + Web(127.0.0.1:3000) 동시 기동
    python scripts/tasks.py dev-api | dev-web
    python scripts/tasks.py test       # 백엔드 pytest + 웹 vitest + 타입검사
    python scripts/tasks.py test-api | test-web | build-web

프로젝트 venv의 python으로 실행하세요 (Windows: .venv\\Scripts\\python, POSIX: .venv/bin/python).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT / "apps" / "api")]),
}
PY = sys.executable


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=cwd, env=ENV)


def node_bin(script: str) -> list[str]:
    """npm 래퍼(.cmd) 없이 node로 직접 실행 — 셸 차이 회피."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        sys.exit("node를 찾을 수 없습니다. Node.js 24 LTS를 설치하세요.")
    return [node, str(WEB / "node_modules" / script)]


def npm(*args: str) -> int:
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_cmd:
        sys.exit("npm을 찾을 수 없습니다.")
    return run([npm_cmd, *args], cwd=WEB)


def setup() -> int:
    return run([PY, "-m", "pip", "install", "-r", "requirements.lock"]) or npm("ci")


def migrate() -> int:
    sys.path[:0] = [str(ROOT / "backend")]
    from namecraft.config import get_settings
    from namecraft.db import migrate as m

    m.upgrade(get_settings().resolved_database_url)
    print("migrated:", get_settings().resolved_database_url)
    return 0


API_CMD = [PY, "-m", "uvicorn", "namecraft_api.main:create_app", "--factory", "--host", "127.0.0.1",
           "--port", "8000", "--reload", "--reload-dir", "backend", "--reload-dir", "apps/api"]


def kill_tree(proc: subprocess.Popen) -> None:
    """Windows에서는 terminate()가 손자 프로세스(uvicorn reload worker)를 남기므로 트리 전체 종료."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.call(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()


def dev_api() -> int:
    migrate()
    return run(API_CMD)


def dev_web() -> int:
    return run(node_bin("next/dist/bin/next") + ["dev", "-H", "127.0.0.1", "-p", "3000"], cwd=WEB)


def dev() -> int:
    migrate()
    api = subprocess.Popen(API_CMD, cwd=ROOT, env=ENV)
    web = subprocess.Popen(node_bin("next/dist/bin/next") + ["dev", "-H", "127.0.0.1", "-p", "3000"], cwd=WEB, env=ENV)
    try:
        return web.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        kill_tree(web)
        kill_tree(api)


def test_api() -> int:
    return run([PY, "-m", "pytest"])


def test_web() -> int:
    return run(node_bin("vitest/vitest.mjs") + ["run"], cwd=WEB) or run(
        node_bin("typescript/bin/tsc") + ["--noEmit"], cwd=WEB)


def build_web() -> int:
    return run(node_bin("next/dist/bin/next") + ["build"], cwd=WEB)


def test() -> int:
    results = {"api": test_api(), "web": test_web()}
    print("\n== summary ==", {k: "PASS" if v == 0 else "FAIL" for k, v in results.items()})
    return 1 if any(results.values()) else 0


TASKS = {"setup": setup, "migrate": migrate, "dev": dev, "dev-api": dev_api, "dev-web": dev_web,
         "test": test, "test-api": test_api, "test-web": test_web, "build-web": build_web}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        print(__doc__)
        sys.exit(2)
    sys.exit(TASKS[sys.argv[1]]())
