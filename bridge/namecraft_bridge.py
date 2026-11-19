#!/usr/bin/env python3
"""NameCraft 연결 브리지 — Claude Code·Antigravity CLI 가 설치된 곳에서 실행하는 작은 HTTP 서버.

NameCraft 앱이 이 브리지에 '이름 후보 생성' 요청을 보내면, 브리지가 이 컴퓨터의 공식 CLI 를
비대화형(-p) 텍스트 모드로 실행해 결과를 돌려준다. 구독형 계정만 사용하며 유료 API 키를 쓰지 않는다.

  python3 namecraft_bridge.py                 # 이 컴퓨터 안에서만 접속 허용(127.0.0.1:8787)
  python3 namecraft_bridge.py --lan           # 같은 네트워크의 다른 PC 에서도 접속 허용(주의)
  python3 namecraft_bridge.py --port 9000 --claude /path/to/claude --agy /path/to/agy

안전 규칙
- 표준 라이브러리만 사용(파일 하나로 다른 PC 에 복사해 실행 가능).
- 모든 요청에 Bearer 토큰 필요(처음 실행 시 ~/.namecraft-bridge/token 생성, 권한 600).
- 실행 가능한 것은 claude·agy 두 CLI 뿐. 요청에서 명령·옵션을 받지 않는다(임의 명령 실행 불가).
- CLI 는 도구 없는/plan 모드 텍스트 작업으로, 빈 임시 폴더에서, 유료 API 키 환경변수를 지운 채 실행.
- 프롬프트·결과 내용은 로그에 남기지 않는다. 한 번에 한 요청만 처리, 요청 크기 64KB 제한.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BRIDGE_VERSION = "1.0.0"
MAX_BODY = 64 * 1024
DEFAULT_PORT = 8787
TOKEN_DIR = Path.home() / ".namecraft-bridge"

_ENV_DENY_PREFIX = ("ANTHROPIC_", "GEMINI_", "GOOGLE_API", "GOOGLE_GENAI", "OPENAI_", "VERTEX", "AWS_BEARER")
_ENV_DENY_SUFFIX = ("_API_KEY", "_API_TOKEN", "_AUTH_TOKEN")
FORBIDDEN_FLAGS = ("--bare", "--dangerously-skip-permissions", "--allow-dangerously-skip-permissions",
                   "--remote-agent", "--remote-control")


def sanitized_env() -> dict:
    env = dict(os.environ)
    for k in list(env):
        ku = k.upper()
        if ku.startswith(_ENV_DENY_PREFIX) or ku.endswith(_ENV_DENY_SUFFIX):
            env.pop(k)
    return env


# NameCraft 백엔드(backend/namecraft/ai_gateway/providers.py)와 같은 인자 — 테스트로 일치 확인
def claude_args(json_schema: dict | None, model_id: str | None) -> list[str]:
    args = ["-p", "--output-format", "json", "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
    return args + (["--model", model_id] if model_id else [])


def agy_args(json_schema: dict | None, model_id: str | None, timeout_s: int) -> list[str]:
    args = ["-p", "--output-format", "json", "--mode", "plan", "--sandbox", "--disable-slash-commands",
            "--print-timeout", f"{timeout_s}s"]
    if json_schema:
        args += ["--json-schema", json.dumps(json_schema, ensure_ascii=False)]
    return args + (["--model", model_id] if model_id else [])


def parse_output(provider: str, stdout: str) -> tuple[str, dict]:
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout, {}
    if not isinstance(doc, dict):
        return stdout, {}
    if provider == "claude_code":
        return str(doc.get("result", "")), {"usage": doc.get("usage")}  # total_cost_usd 등 API 과금 필드는 버림
    for key in ("result", "response", "text", "output"):
        if isinstance(doc.get(key), (str, dict, list)):
            v = doc[key]
            return (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)), {"usage": doc.get("usage"),
                                                                                      "model": doc.get("model")}
    return stdout, {}


class Bridge:
    def __init__(self, commands: dict[str, list[str] | None], token: str):
        self.commands = commands
        self.token = token
        self.lock = threading.Lock()  # 한 번에 한 요청(구독 한도·자원 보호)

    def info(self) -> dict:
        out = {}
        for pid, cmd in self.commands.items():
            ver = None
            if cmd:
                try:
                    p = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=20,
                                       stdin=subprocess.DEVNULL, env=sanitized_env())
                    ver = p.stdout.strip().splitlines()[0] if p.returncode == 0 and p.stdout.strip() else None
                except (OSError, subprocess.TimeoutExpired):
                    ver = None
            out[pid] = {"found": bool(cmd and ver), "version": ver}
        return out

    def generate(self, req: dict) -> tuple[int, dict]:
        pid = req.get("provider")
        if pid not in self.commands:
            return 400, {"error": "unknown_provider"}
        cmd = self.commands[pid]
        if not cmd:
            return 503, {"error": "unavailable", "message": f"{pid} CLI 를 이 컴퓨터에서 찾지 못했습니다."}
        system, prompt = req.get("system"), req.get("prompt")
        if not isinstance(system, str) or not isinstance(prompt, str):
            return 400, {"error": "bad_request"}
        timeout_s = int(min(max(int(req.get("timeout_s") or 120), 10), 600))
        model_id = req.get("model_id") if isinstance(req.get("model_id"), str) and req.get("model_id") else None
        schema = req.get("json_schema") if isinstance(req.get("json_schema"), dict) else None
        args = claude_args(schema, model_id) if pid == "claude_code" else agy_args(schema, model_id, timeout_s)
        full = cmd + args
        if any(f in full for f in FORBIDDEN_FLAGS):
            return 400, {"error": "forbidden_flag"}
        if not self.lock.acquire(timeout=5):
            return 429, {"error": "busy", "message": "다른 요청을 처리 중입니다."}
        try:
            t = time.monotonic()
            with tempfile.TemporaryDirectory(prefix="namecraft-bridge-", ignore_cleanup_errors=True) as cwd:
                try:
                    p = subprocess.run(full, input=system + "\n\n" + prompt, capture_output=True, text=True,
                                       encoding="utf-8", timeout=timeout_s, cwd=cwd, env=sanitized_env())
                except subprocess.TimeoutExpired:
                    return 504, {"error": "timeout"}
                except OSError:
                    return 503, {"error": "unavailable"}
            ms = int((time.monotonic() - t) * 1000)
        finally:
            self.lock.release()
        err = (p.stderr or "").lower()
        if p.returncode != 0:
            if "rate limit" in err or "usage limit" in err or "quota" in err:
                return 429, {"error": "rate_limited"}
            if "login" in err or "auth" in err:
                return 503, {"error": "auth_required", "message": "이 컴퓨터에서 CLI 로그인이 필요합니다."}
            return 502, {"error": "process_error", "exit_code": p.returncode}
        text, meta = parse_output(pid, p.stdout)
        usage = meta.get("usage") or {}
        return 200, {"text": text, "model_id": meta.get("model") or model_id, "duration_ms": ms,
                     "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens")}


def make_handler(bridge: Bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NameCraftBridge/" + BRIDGE_VERSION

        def log_message(self, fmt, *args):  # 경로·상태만, 내용 없음
            sys.stderr.write("%s %s %s\n" % (time.strftime("%H:%M:%S"), self.command, args[1] if len(args) > 1 else ""))

        def _send(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            h = self.headers.get("Authorization", "")
            ok = h.lower().startswith("bearer ") and hmac.compare_digest(h[7:].strip().encode(), bridge.token.encode())
            if not ok:
                self._send(401, {"error": "unauthorized"})
            return ok

        def do_GET(self):
            if self.path != "/health":
                return self._send(404, {"error": "not_found"})
            if not self._authed():
                return
            self._send(200, {"ok": True, "bridge_version": BRIDGE_VERSION, "providers": bridge.info()})

        def do_POST(self):
            if self.path != "/generate":
                return self._send(404, {"error": "not_found"})
            if not self._authed():
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": "too_large"})
            try:
                req = json.loads(self.rfile.read(n))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._send(400, {"error": "bad_json"})
            code, obj = bridge.generate(req if isinstance(req, dict) else {})
            self._send(code, obj)

    return Handler


def load_token(token_dir: Path = TOKEN_DIR, rotate: bool = False) -> str:
    token_dir.mkdir(parents=True, exist_ok=True)
    f = token_dir / "token"
    if f.exists() and not rotate:
        t = f.read_text(encoding="utf-8").strip()
        if t:
            return t
    t = secrets.token_urlsafe(32)
    f.write_text(t, encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    return t


def resolve(name: str, given: str | None) -> list[str] | None:
    if given:
        return [given]
    found = shutil.which(name)
    if not found:  # 흔한 설치 위치(사용자 홈의 .local/bin) — 탐색이 아니라 고정 경로 1곳 확인
        cand = Path.home() / ".local" / "bin" / name
        found = str(cand) if cand.exists() else None
    return [found] if found else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NameCraft 연결 브리지 (Claude Code·Antigravity)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--lan", action="store_true", help="같은 네트워크의 다른 PC 접속 허용(0.0.0.0)")
    ap.add_argument("--claude", help="claude 실행 파일 경로(기본: 자동)")
    ap.add_argument("--agy", help="agy 실행 파일 경로(기본: 자동)")
    ap.add_argument("--new-token", action="store_true", help="토큰 새로 만들기(이전 토큰 무효)")
    a = ap.parse_args(argv)
    token = load_token(rotate=a.new_token)
    bridge = Bridge({"claude_code": resolve("claude", a.claude), "antigravity": resolve("agy", a.agy)}, token)
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, a.port), make_handler(bridge))
    info = bridge.info()
    print("NameCraft 연결 브리지", BRIDGE_VERSION)
    for pid, i in info.items():
        print(f"  {pid:<12} {'찾음 ' + i['version'] if i['found'] else '없음'}")
    shown = "이 컴퓨터의 IP" if a.lan else "127.0.0.1"
    print(f"\n  NameCraft 설정 화면에 입력할 값")
    print(f"    주소 : http://{shown}:{a.port}")
    print(f"    토큰 : {token}")
    if a.lan:
        print("\n  ⚠ 같은 네트워크의 다른 기기에서도 접속할 수 있습니다. 토큰을 공유하지 말고, 인터넷에 노출하지 마세요.")
    print("\n  끄기: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
