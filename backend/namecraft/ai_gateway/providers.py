"""실제 AI Provider 어댑터 (기획서 §29, §31, §33).

공통 원칙
- 유료 API 키를 읽거나 전달하지 않는다. 서브프로세스 환경에서 *_API_KEY 류 변수를 제거한다.
- 인증 캐시·쿠키·세션 파일을 읽지 않는다. CLI 는 사용자가 지정한 명령만 실행한다(경로 강제 탐색 금지).
- 구독형 CLI(Claude Code, Antigravity)는 기본 비활성. 사용자가 켜야 공식 비대화형 모드로만 실행한다.
- 이름 생성은 '도구 없는 순수 텍스트 작업'으로 제한한다(빈 임시 작업 폴더, 도구 비활성/plan 모드).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from namecraft.ai_gateway.protocols import (
    Capability as C,
    CapabilityLevel as L,
    ConnectionState,
    ExecutionMode,
    ProviderId,
    SourceKind,
)

# 서브프로세스에 절대 넘기지 않는 환경변수 (접두어/정확 일치)
_ENV_DENY_PREFIX = ("ANTHROPIC_", "GEMINI_", "GOOGLE_API", "GOOGLE_GENAI", "OPENAI_", "VERTEX", "AWS_BEARER")
_ENV_DENY_SUFFIX = ("_API_KEY", "_API_TOKEN", "_AUTH_TOKEN")
FORBIDDEN_FLAGS = ("--bare", "--dangerously-skip-permissions", "--allow-dangerously-skip-permissions",
                   "--remote-agent", "--remote-control")


def sanitized_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for k in list(env):
        ku = k.upper()
        if ku.startswith(_ENV_DENY_PREFIX) or ku.endswith(_ENV_DENY_SUFFIX):
            env.pop(k)
    return env


class ProviderCallError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # unavailable | timeout | rate_limited | invalid_output | process_error | disabled


@dataclass
class ProviderResult:
    text: str
    model_id: str | None
    duration_ms: int
    tokens_in: int | None = None
    tokens_out: int | None = None
    raw_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderSettings:
    enabled: bool = False
    command: list[str] | None = None  # 사용자가 지정한 실행 명령 (예: ["claude"] 또는 ["wsl.exe","-e","/home/u/.local/bin/claude"])
    model_id: str | None = None
    timeout_s: int = 120
    base_url: str = "http://127.0.0.1:11434"  # Ollama
    connection: str = "local"  # local | bridge (Claude Code·Antigravity)
    bridge_url: str | None = None
    bridge_token: str | None = None


# ---------------------------------------------------------------- Ollama

class OllamaProvider:
    id = ProviderId.ollama

    def __init__(self, settings: ProviderSettings | None = None):
        self.s = settings or ProviderSettings(enabled=True)

    def _get(self, path: str, timeout: float = 3.0) -> dict:
        with urllib.request.urlopen(self.s.base_url + path, timeout=timeout) as r:  # 로컬 전용
            return json.loads(r.read())

    def _post(self, path: str, body: dict, timeout: float) -> dict:
        req = urllib.request.Request(self.s.base_url + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def list_models(self) -> list[dict]:
        models = []
        for m in self._get("/api/tags").get("models", []):
            name = m.get("name") or m.get("model")
            caps: list[str] | None = None
            try:
                caps = self._post("/api/show", {"model": name}, timeout=5).get("capabilities")
            except Exception:  # 구버전: capabilities 미제공
                caps = None
            family = (m.get("details") or {}).get("family", "")
            if caps is None:
                caps = ["embedding"] if "bert" in family or "embed" in (name or "") else ["completion"]
            models.append({"name": name, "family": family, "size": m.get("size"), "capabilities": caps,
                           "can_generate": "completion" in caps,
                           "is_remote": bool(m.get("remote_host") or m.get("remote_model")
                                             or (name or "").endswith((":cloud", "-cloud")))})
        return models

    async def capabilities(self) -> dict[C, L]:
        return {C.healthcheck: L.supported, C.list_models: L.supported, C.generate_candidates: L.supported,
                C.explain_name: L.supported, C.summarize_comparison: L.supported, C.observe_usage: L.supported,
                C.observe_quota: L.not_applicable}

    async def connection_status(self) -> dict[str, Any]:
        return self.status()

    def status(self) -> dict[str, Any]:
        base = {"provider_id": self.id.value, "label": "Ollama", "source_kind": SourceKind.local_observed,
                "is_mock": False, "enabled": self.s.enabled, "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        try:
            version = self._get("/api/version").get("version")
            models = self.list_models()
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            return {**base, "state": ConnectionState.not_installed, "execution_mode": ExecutionMode.unavailable,
                    "message": "로컬 Ollama 서버(127.0.0.1:11434)에 연결할 수 없습니다. Ollama 앱을 실행하세요.",
                    "models": [], "version": None}
        gen = [m for m in models if m["can_generate"] and not m["is_remote"]]
        if not self.s.enabled:
            return {**base, "state": ConnectionState.disabled, "execution_mode": ExecutionMode.unavailable,
                    "message": f"Ollama {version} 확인됨 — 사용 안 함으로 설정되어 있습니다.", "models": models,
                    "version": version, "selected_model": None, "reason": "disabled_by_user"}
        selected = self.s.model_id if self.s.model_id in {m["name"] for m in gen} else (gen[0]["name"] if gen else None)
        if not gen:
            msg = "생성 가능한 모델이 없습니다(임베딩 전용 모델만 있음). 예: `ollama pull <모델>` 후 다시 확인하세요." if models \
                else "설치된 모델이 없습니다. `ollama pull <모델>` 로 모델을 받으세요."
            return {**base, "state": ConnectionState.connected, "execution_mode": ExecutionMode.unavailable,
                    "message": msg, "models": models, "version": version, "selected_model": None,
                    "reason": "no_generation_model"}
        return {**base, "state": ConnectionState.connected, "execution_mode": ExecutionMode.native_local,
                "message": f"로컬 모델 사용 가능: {selected}", "models": models, "version": version,
                "selected_model": selected}


    async def generate(self, task: str, payload: dict, policy: dict) -> dict:
        """AIProvider 프로토콜 구현 — policy: {system, prompt, json_schema, seed, model_id}."""
        r = self.generate_text(policy["prompt"], system=policy["system"], json_schema=policy.get("json_schema"),
                               seed=policy.get("seed"), model_id=policy.get("model_id"))
        return {"task": task, "text": r.text, "model_id": r.model_id, "duration_ms": r.duration_ms,
                "tokens_in": r.tokens_in, "tokens_out": r.tokens_out}

    def generate_text(self, prompt: str, *, system: str, json_schema: dict | None, seed: int | None,
                      model_id: str) -> ProviderResult:
        body: dict[str, Any] = {"model": model_id, "stream": False,
                                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                                "options": {"temperature": 0.7, **({"seed": seed} if seed is not None else {})}}
        if json_schema:
            body["format"] = json_schema
        t = time.monotonic()
        try:
            r = self._post("/api/chat", body, timeout=self.s.timeout_s)
        except TimeoutError as e:
            raise ProviderCallError("timeout", "Ollama 응답 시간 초과") from e
        except urllib.error.HTTPError as e:
            raise ProviderCallError("process_error", f"Ollama 오류 {e.code}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ProviderCallError("unavailable", "Ollama 연결 실패") from e
        return ProviderResult(text=(r.get("message") or {}).get("content", ""), model_id=r.get("model", model_id),
                              duration_ms=int((time.monotonic() - t) * 1000),
                              tokens_in=r.get("prompt_eval_count"), tokens_out=r.get("eval_count"),
                              raw_meta={k: r.get(k) for k in ("total_duration", "eval_duration", "eval_count")})


# ---------------------------------------------------------------- 구독형 CLI 공통

_WSL_CACHE: dict[str, str | None] = {}


def wsl_lookup(name: str) -> str | None:
    """Windows 백엔드에서 WSL 안에 설치된 CLI 위치 확인 — WSL 로그인 셸의 PATH 로 `command -v` 만 실행.
    (파일 시스템 탐색·인증 파일 접근 없음, 프로세스당 1회 캐시)"""
    if name in _WSL_CACHE:
        return _WSL_CACHE[name]
    path = None
    if os.name == "nt" and shutil.which("wsl.exe"):
        try:
            p = subprocess.run(["wsl.exe", "-e", "bash", "-lc", f"command -v {name}"], capture_output=True,
                               text=True, timeout=15, stdin=subprocess.DEVNULL)  # 서버 워커는 stdin 이 없을 수 있음
            out = p.stdout.strip().splitlines()
            path = out[-1] if p.returncode == 0 and out and out[-1].startswith("/") else None
        except (OSError, subprocess.TimeoutExpired):
            path = None
    _WSL_CACHE[name] = path
    return path


class _CliProvider:
    id: ProviderId
    label: str
    default_command: str
    prompt_via_stdin = True  # Claude Code: -p 뒤 프롬프트를 표준입력으로. Antigravity: --print=<프롬프트>

    def __init__(self, settings: ProviderSettings | None = None):
        self.s = settings or ProviderSettings()
        self.detected_via: str | None = None

    def resolved_command(self) -> list[str] | None:
        if self.s.command:
            self.detected_via = "configured"
            return list(self.s.command)
        found = shutil.which(self.default_command)  # 현재 PATH
        if found:
            self.detected_via = "path"
            return [found]
        wsl = wsl_lookup(self.default_command)  # Windows 에서 WSL 안에 설치된 경우
        if wsl:
            self.detected_via = "wsl"
            return ["wsl.exe", "-e", wsl]
        self.detected_via = None
        return None

    def _run(self, args: list[str], *, stdin: str | None = None, timeout: float = 10) -> subprocess.CompletedProcess:
        cmd = self.resolved_command()
        if not cmd:
            raise ProviderCallError("unavailable", f"{self.label} CLI 를 찾을 수 없습니다.")
        full = cmd + args
        if any(f in full for f in FORBIDDEN_FLAGS):  # 방어적 점검
            raise ProviderCallError("process_error", "금지된 CLI 옵션")
        # 빈 작업 폴더 — 프로젝트 파일 접근 차단. Windows 에서 자식 프로세스가 폴더를 잡고 있으면 정리 실패를 무시
        with tempfile.TemporaryDirectory(prefix="namecraft-ai-", ignore_cleanup_errors=True) as cwd:
            try:
                return subprocess.run(full, input=stdin, capture_output=True, text=True, encoding="utf-8",
                                      timeout=timeout, cwd=cwd, env=sanitized_env(),
                                      **({} if stdin is not None else {"stdin": subprocess.DEVNULL}))
            except subprocess.TimeoutExpired as e:
                raise ProviderCallError("timeout", f"{self.label} 응답 시간 초과") from e
            except OSError as e:
                raise ProviderCallError("unavailable", f"{self.label} 실행 실패") from e

    def version(self) -> str | None:
        try:
            p = self._run(["--version"], timeout=15)
        except ProviderCallError:
            return None
        return p.stdout.strip().splitlines()[0] if p.returncode == 0 and p.stdout.strip() else None

    async def connection_status(self) -> dict[str, Any]:
        return self.status()

    # ------------------------------------------------------------ 연결 브리지
    def _bridge(self, method: str, path: str, body: dict | None = None, timeout: float = 10) -> dict:
        if not self.s.bridge_url or not self.s.bridge_token:
            raise ProviderCallError("unavailable", "브리지 주소와 토큰을 설정하세요.")
        req = urllib.request.Request(self.s.bridge_url.rstrip("/") + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self.s.bridge_token}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read()).get("error", "")
            except Exception:
                err = ""
            kind = {401: "auth_required", 429: "rate_limited" if err == "rate_limited" else "busy",
                    504: "timeout"}.get(e.code, "unavailable" if err in ("unavailable", "auth_required") else "process_error")
            msg = {"unauthorized": "브리지 토큰이 맞지 않습니다.", "auth_required": "브리지 쪽 컴퓨터에서 CLI 로그인이 필요합니다.",
                   "busy": "브리지가 다른 요청을 처리 중입니다.", "rate_limited": f"{self.label} 사용 한도에 도달했습니다.",
                   "unavailable": f"브리지 쪽 컴퓨터에서 {self.label} 를 찾지 못했습니다."}.get(err, f"브리지 오류({e.code})")
            raise ProviderCallError(kind, msg) from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise ProviderCallError("unavailable", "브리지에 연결할 수 없습니다. 브리지가 실행 중인지, 주소가 맞는지 확인하세요.") from e

    def _bridge_status(self, base: dict) -> dict[str, Any]:
        base = {**base, "connection": "bridge", "bridge_url": self.s.bridge_url,
                "bridge_token_set": bool(self.s.bridge_token), "command": None, "detected_via": "bridge"}
        try:
            info = self._bridge("GET", "/health", timeout=8)
        except ProviderCallError as e:
            return {**base, "state": ConnectionState.not_installed if e.kind == "unavailable" else ConnectionState.auth_required,
                    "execution_mode": ExecutionMode.manual_handoff, "message": str(e), "version": None}
        mine = (info.get("providers") or {}).get(self.id.value) or {}
        if not mine.get("found"):
            return {**base, "state": ConnectionState.not_installed, "execution_mode": ExecutionMode.manual_handoff,
                    "message": f"브리지에 연결됐지만 그쪽 컴퓨터에 {self.label} 가 없습니다.", "version": None}
        ver = mine.get("version")
        if not self.s.enabled:
            return {**base, "state": ConnectionState.disabled, "execution_mode": ExecutionMode.manual_handoff,
                    "message": f"브리지로 {self.label} {ver} 찾음 — 꺼져 있습니다. '사용하기'를 누르면 바로 쓸 수 있습니다.",
                    "version": ver}
        return {**base, "state": ConnectionState.connected, "execution_mode": ExecutionMode.supported_cli_task,
                "message": f"브리지로 {self.label} {ver} 사용 중", "version": ver, "selected_model": self.s.model_id}

    def status(self) -> dict[str, Any]:
        base = {"provider_id": self.id.value, "label": self.label, "is_mock": False, "enabled": self.s.enabled,
                "source_kind": SourceKind.local_observed, "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "models": [], "command_configured": bool(self.s.command), "connection": "local"}
        if self.s.connection == "bridge":
            return self._bridge_status(base)
        cmd = self.resolved_command()
        ver = self.version() if cmd else None
        base["command"] = cmd
        base["detected_via"] = self.detected_via
        if not cmd or not ver:
            return {**base, "state": ConnectionState.not_installed, "execution_mode": ExecutionMode.manual_handoff,
                    "message": f"{self.label} 이(가) 이 PC 에서 보이지 않습니다(Windows PATH·WSL 모두 확인). 설치되어 있다면 설정에서 실행 명령을 직접 지정하세요.",
                    "version": None}
        if not self.s.enabled:
            return {**base, "state": ConnectionState.disabled, "execution_mode": ExecutionMode.manual_handoff,
                    "message": f"{self.label} {ver} 찾음{' (WSL)' if self.detected_via == 'wsl' else ''} — 꺼져 있습니다. '사용하기'를 누르면 바로 쓸 수 있습니다.",
                    "version": ver}
        return {**base, "state": ConnectionState.connected, "execution_mode": ExecutionMode.supported_cli_task,
                "message": f"{self.label} {ver} — 공식 비대화형 모드로 실행합니다(로그인·구독 한도는 해당 서비스 기준).",
                "version": ver, "selected_model": self.s.model_id}

    def build_args(self, *, json_schema: dict | None, model_id: str | None, prompt: str | None = None) -> list[str]:
        raise NotImplementedError

    def parse_output(self, stdout: str) -> tuple[str, dict]:
        raise NotImplementedError


    async def generate(self, task: str, payload: dict, policy: dict) -> dict:
        """AIProvider 프로토콜 구현 — policy: {system, prompt, json_schema, seed, model_id}."""
        r = self.generate_text(policy["prompt"], system=policy["system"], json_schema=policy.get("json_schema"),
                               seed=policy.get("seed"), model_id=policy.get("model_id"))
        return {"task": task, "text": r.text, "model_id": r.model_id, "duration_ms": r.duration_ms,
                "tokens_in": r.tokens_in, "tokens_out": r.tokens_out}

    def generate_text(self, prompt: str, *, system: str, json_schema: dict | None, seed: int | None,
                      model_id: str | None) -> ProviderResult:
        if not self.s.enabled:
            raise ProviderCallError("disabled", f"{self.label} 실행 연동이 꺼져 있습니다.")
        if self.s.connection == "bridge":
            r = self._bridge("POST", "/generate", {"provider": self.id.value, "system": system, "prompt": prompt,
                                                   "json_schema": json_schema, "model_id": model_id or self.s.model_id,
                                                   "timeout_s": self.s.timeout_s}, timeout=self.s.timeout_s + 15)
            return ProviderResult(text=r.get("text", ""), model_id=r.get("model_id"), duration_ms=r.get("duration_ms") or 0,
                                  tokens_in=r.get("tokens_in"), tokens_out=r.get("tokens_out"), raw_meta={"via": "bridge"})
        full_prompt = system + "\n\n" + prompt
        args = self.build_args(json_schema=json_schema, model_id=model_id or self.s.model_id,
                               prompt=None if self.prompt_via_stdin else full_prompt)
        t = time.monotonic()
        p = self._run(args, stdin=full_prompt if self.prompt_via_stdin else None, timeout=self.s.timeout_s)
        dur = int((time.monotonic() - t) * 1000)
        err = (p.stderr or "").lower()
        if p.returncode != 0:
            if "rate limit" in err or "usage limit" in err or "quota" in err:
                raise ProviderCallError("rate_limited", f"{self.label} 사용 한도에 도달했습니다.")
            if "login" in err or "auth" in err:
                raise ProviderCallError("unavailable", f"{self.label} 로그인이 필요합니다.")
            raise ProviderCallError("process_error", f"{self.label} 실행 오류(종료 코드 {p.returncode})")
        text, meta = self.parse_output(p.stdout)
        usage = meta.get("usage") or {}
        return ProviderResult(text=text, model_id=meta.get("model") or model_id or self.s.model_id, duration_ms=dur,
                              tokens_in=usage.get("input_tokens"), tokens_out=usage.get("output_tokens"),
                              raw_meta={k: v for k, v in meta.items() if k in ("usage", "model", "num_turns")})


class ClaudeCodeProvider(_CliProvider):
    id = ProviderId.claude_code
    label = "Claude Code"
    default_command = "claude"

    async def capabilities(self) -> dict[C, L]:
        return {C.healthcheck: L.supported, C.list_models: L.conditional, C.generate_candidates: L.conditional,
                C.explain_name: L.conditional, C.summarize_comparison: L.conditional, C.observe_usage: L.manual,
                C.observe_quota: L.manual}

    def build_args(self, *, json_schema: dict | None, model_id: str | None, prompt: str | None = None) -> list[str]:
        args = ["-p", "--output-format", "json", "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
        if model_id:
            args += ["--model", model_id]
        return args

    def parse_output(self, stdout: str) -> tuple[str, dict]:
        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout, {}
        if isinstance(doc, dict):
            # total_cost_usd 등 API 과금 필드는 구독 사용량과 다르므로 저장하지 않는다(§30.2)
            return str(doc.get("result", "")), {"usage": doc.get("usage"), "num_turns": doc.get("num_turns")}
        return stdout, {}


class AntigravityProvider(_CliProvider):
    id = ProviderId.antigravity
    label = "Google Antigravity"
    default_command = "agy"
    prompt_via_stdin = False  # agy 의 -p/--print 는 값으로 프롬프트를 받는다(--print=<프롬프트>)

    async def capabilities(self) -> dict[C, L]:
        return {C.healthcheck: L.supported, C.list_models: L.supported, C.generate_candidates: L.conditional,
                C.explain_name: L.conditional, C.summarize_comparison: L.conditional, C.observe_usage: L.manual,
                C.observe_quota: L.manual}

    def build_args(self, *, json_schema: dict | None, model_id: str | None, prompt: str | None = None) -> list[str]:
        # --disable-slash-commands 는 쓰지 않는다: 켜면 '--mode plan(파일 수정 안 함)'이 무시된다는 CLI 경고가 있음.
        # 프롬프트는 항상 고정 안내문으로 시작하므로 '/' 명령으로 해석될 수 없다.
        args = [f"--print={prompt or ''}", "--output-format", "json", "--mode", "plan", "--sandbox",
                "--print-timeout", f"{self.s.timeout_s}s"]
        if json_schema:
            args += ["--json-schema", json.dumps(json_schema, ensure_ascii=False)]
        if model_id:
            args += ["--model", model_id]
        return args

    def parse_output(self, stdout: str) -> tuple[str, dict]:
        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout, {}
        if isinstance(doc, dict):
            if isinstance(doc.get("structured_output"), dict):  # --json-schema 로 검증된 구조화 출력
                return json.dumps(doc["structured_output"], ensure_ascii=False), {"usage": doc.get("usage"),
                                                                                  "model": doc.get("model")}
            for key in ("result", "response", "text", "output"):
                if isinstance(doc.get(key), (str, dict, list)):
                    val = doc[key]
                    return (val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)), \
                        {"usage": doc.get("usage"), "model": doc.get("model")}
        return stdout, {}


def build_providers(settings: dict[str, ProviderSettings]) -> dict[str, Any]:
    return {
        "ollama": OllamaProvider(settings.get("ollama") or ProviderSettings(enabled=True)),
        "claude_code": ClaudeCodeProvider(settings.get("claude_code") or ProviderSettings()),
        "antigravity": AntigravityProvider(settings.get("antigravity") or ProviderSettings()),
    }
