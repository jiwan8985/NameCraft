"""Phase 1 mock Provider/Collector.

- 실제 프로세스 실행·네트워크 호출·파일 탐색을 하지 않는다.
- 모든 응답에 `is_mock: True`, `source_kind: mock`을 붙인다 (REQ-USG-008).
- 기본 상태는 docs/AI_CAPABILITY_MATRIX.md 초기 판정을 반영한다.
"""

from __future__ import annotations

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
from namecraft.errors import ProviderUnavailable

_MATRIX: dict[ProviderId, dict[C, L]] = {
    ProviderId.ollama: {
        C.healthcheck: L.supported, C.list_models: L.supported, C.generate_candidates: L.supported,
        C.explain_name: L.supported, C.summarize_comparison: L.supported,
        C.observe_usage: L.supported, C.observe_quota: L.not_applicable,
    },
    ProviderId.claude_code: {
        C.healthcheck: L.supported, C.list_models: L.conditional, C.generate_candidates: L.conditional,
        C.explain_name: L.conditional, C.summarize_comparison: L.conditional,
        C.observe_usage: L.manual, C.observe_quota: L.manual,
    },
    ProviderId.antigravity: {
        C.healthcheck: L.supported, C.list_models: L.supported, C.generate_candidates: L.conditional,
        C.explain_name: L.conditional, C.summarize_comparison: L.conditional,
        C.observe_usage: L.manual, C.observe_quota: L.manual,
    },
}

_LABELS = {
    ProviderId.ollama: "Ollama",
    ProviderId.claude_code: "Claude Code",
    ProviderId.antigravity: "Google Antigravity",
}


@dataclass
class MockProvider:
    id: str
    state: ConnectionState
    mode: ExecutionMode
    message: str
    models: list[str] = field(default_factory=list)

    async def capabilities(self) -> dict[C, L]:
        return dict(_MATRIX[ProviderId(self.id)])

    async def connection_status(self) -> dict[str, Any]:
        return {
            "provider_id": self.id,
            "label": _LABELS[ProviderId(self.id)],
            "state": self.state,
            "execution_mode": self.mode,
            "message": self.message,
            "models": self.models,
            "last_checked_at": None,
            "source_kind": SourceKind.mock,
            "is_mock": True,
        }

    async def generate(self, task: str, payload: dict, policy: dict) -> dict:
        # Phase 1에서는 생성하지 않는다 — 규칙 기반 폴백 경로를 안내.
        raise ProviderUnavailable(
            "Phase 1 mock: AI 생성은 아직 연결되지 않았습니다. 규칙 기반 엔진(Phase 6)을 사용하세요.",
            details={"provider_id": self.id, "fallback": "rule_based", "is_mock": True},
        )


@dataclass
class MockUsageCollector:
    provider_id: str

    async def capabilities(self) -> dict[C, L]:
        caps = _MATRIX[ProviderId(self.provider_id)]
        return {C.observe_usage: caps[C.observe_usage], C.observe_quota: caps[C.observe_quota]}

    async def collect(self, since: Any = None) -> list[dict]:
        return []  # mock: 수집하지 않음. 숫자를 꾸며내지 않는다.


def default_mock_providers() -> list[MockProvider]:
    return [
        MockProvider(ProviderId.ollama, ConnectionState.unknown, ExecutionMode.unavailable,
                     "mock: 로컬 Ollama 탐지는 Phase 7에서 구현됩니다."),
        MockProvider(ProviderId.claude_code, ConnectionState.disabled, ExecutionMode.manual_handoff,
                     "mock: 기본 비활성. 사용자가 켜면 공식 CLI 비대화형 모드만 사용합니다."),
        MockProvider(ProviderId.antigravity, ConnectionState.disabled, ExecutionMode.manual_handoff,
                     "mock: 기본 비활성. 사용자가 켜면 공식 CLI 비대화형 모드만 사용합니다."),
    ]
