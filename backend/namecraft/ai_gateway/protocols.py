"""AI Provider Gateway 인터페이스 (기획서 §29.3).

생성 어댑터(AIProvider)와 사용량 수집 어댑터(UsageCollector)를 분리한다.
Phase 1: 인터페이스 + mock만. 실제 어댑터는 Phase 7(생성)·Phase 11(수집).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class ProviderId(StrEnum):
    ollama = "ollama"
    claude_code = "claude_code"
    antigravity = "antigravity"


class ExecutionMode(StrEnum):
    native_local = "native_local"
    interactive_cli = "interactive_cli"
    supported_cli_task = "supported_cli_task"
    manual_handoff = "manual_handoff"
    monitor_only = "monitor_only"
    unavailable = "unavailable"


class Capability(StrEnum):
    generate_candidates = "generate_candidates"
    explain_name = "explain_name"
    summarize_comparison = "summarize_comparison"
    healthcheck = "healthcheck"
    list_models = "list_models"
    observe_usage = "observe_usage"
    observe_quota = "observe_quota"


class CapabilityLevel(StrEnum):
    supported = "supported"
    conditional = "conditional"
    manual = "manual"
    not_supported = "not_supported"
    not_applicable = "n/a"


class ConnectionState(StrEnum):
    connected = "connected"
    not_installed = "not_installed"
    auth_required = "auth_required"
    disabled = "disabled"  # 사용자가 켜지 않음 (Claude Code/Antigravity 기본값, D-004)
    error = "error"
    unknown = "unknown"


class SourceKind(StrEnum):
    official = "official"
    local_observed = "local_observed"
    manual = "manual"
    estimated = "estimated"
    unknown = "unknown"
    not_supported = "not_supported"
    stale = "stale"
    demo = "demo"
    mock = "mock"


@runtime_checkable
class AIProvider(Protocol):
    id: str

    async def capabilities(self) -> dict[Capability, CapabilityLevel]: ...
    async def connection_status(self) -> dict[str, Any]: ...
    async def generate(self, task: str, payload: dict, policy: dict) -> dict: ...


@runtime_checkable
class UsageCollector(Protocol):
    provider_id: str

    async def capabilities(self) -> dict[Capability, CapabilityLevel]: ...
    async def collect(self, since: Any = None) -> list[dict]: ...
