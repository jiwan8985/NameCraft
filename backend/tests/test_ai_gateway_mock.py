"""Phase 1 게이트(§32): Provider 목록·연결 상태 mock 및 오류 UX."""

from __future__ import annotations

import asyncio

import pytest

from namecraft.ai_gateway import AIProvider, UsageCollector, default_mock_providers
from namecraft.ai_gateway.mock import MockUsageCollector
from namecraft.ai_gateway.protocols import Capability, ExecutionMode
from namecraft.errors import ProviderUnavailable


def test_providers_endpoint_lists_three_mock_providers(client, auth):
    body = client.get("/api/v1/ai/providers", headers=auth).json()
    assert body["verification_status"] == "mock"
    assert any(w["code"] == "mock_data" for w in body["warnings"])
    ids = [p["provider_id"] for p in body["data"]]
    assert ids == ["ollama", "claude_code", "antigravity"]
    for p in body["data"]:
        assert p["is_mock"] is True and p["source_kind"] == "mock"
        assert set(p["capabilities"]) == {c.value for c in Capability}


def test_subscription_providers_default_disabled(client, auth):
    """D-004: Claude Code·Antigravity 기본 manual_handoff/비활성."""
    data = {p["provider_id"]: p for p in client.get("/api/v1/ai/providers", headers=auth).json()["data"]}
    for pid in ("claude_code", "antigravity"):
        assert data[pid]["state"] == "disabled"
        assert data[pid]["execution_mode"] == ExecutionMode.manual_handoff
    assert data["ollama"]["capabilities"]["observe_quota"] == "n/a"  # '무제한 100%' 표기 금지 근거


def test_mock_satisfies_protocols():
    for p in default_mock_providers():
        assert isinstance(p, AIProvider)
        assert isinstance(MockUsageCollector(p.id), UsageCollector)


def test_mock_generate_refuses_with_rule_based_fallback():
    p = default_mock_providers()[0]
    with pytest.raises(ProviderUnavailable) as e:
        asyncio.run(p.generate("generate_candidates", {}, {}))
    assert e.value.details["fallback"] == "rule_based"


def test_mock_collector_fabricates_nothing():
    assert asyncio.run(MockUsageCollector("claude_code").collect()) == []


def test_provider_test_endpoint_is_mock(client, auth):
    body = client.post("/api/v1/ai/providers/claude_code/test", headers=auth).json()
    assert body["data"]["test_result"] == "skipped_mock"
