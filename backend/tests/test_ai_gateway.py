"""Phase 7 게이트: 공식 연동 범위 · AI 응답 검증 · 폴백 · 재현성 (기획서 §21, §32, §33.4)."""

from __future__ import annotations

import asyncio
import json

import pytest

from namecraft.ai_gateway import AIProvider, UsageCollector, default_mock_providers
from namecraft.ai_gateway.mock import MockUsageCollector
from namecraft.ai_gateway.providers import (
    AntigravityProvider, ClaudeCodeProvider, FORBIDDEN_FLAGS, OllamaProvider, ProviderCallError, ProviderSettings,
    sanitized_env,
)
from namecraft.config import Settings
from namecraft.db.models import AIGenerationRecord, AIInvocation, AIProviderSetting
from namecraft.services import ai_generation as aig
from namecraft.services.generation import GenerateRequest

GEN = {"name": "gemma-fake", "caps": ["completion"]}
EMB = {"name": "nomic-embed-text:latest", "caps": ["embedding"], "family": "nomic-bert"}


def _req(**kw):
    return GenerateRequest(surname_hangul="심", syllables=2, name_type="any", count=5, **kw)


# ---------------------------------------------------------------- 탐지

def test_ollama_unreachable_is_reported_not_fabricated():
    st = OllamaProvider(ProviderSettings(enabled=True, base_url="http://127.0.0.1:9")).status()
    assert st["state"] == "not_installed" and st["execution_mode"] == "unavailable" and st["models"] == []


def test_ollama_embedding_only_cannot_generate(fake_ollama):
    f = fake_ollama([EMB])
    st = OllamaProvider(ProviderSettings(enabled=True, base_url=f.url)).status()
    assert st["state"] == "connected" and st["execution_mode"] == "unavailable"
    assert st["reason"] == "no_generation_model" and st["models"][0]["can_generate"] is False


def test_ollama_with_generation_model(fake_ollama):
    f = fake_ollama([EMB, GEN])
    st = OllamaProvider(ProviderSettings(enabled=True, base_url=f.url)).status()
    assert st["execution_mode"] == "native_local" and st["selected_model"] == "gemma-fake"


def test_cli_not_installed_and_disabled_states(fake_cli):
    missing = ClaudeCodeProvider(ProviderSettings(command=["definitely-not-a-real-cli-xyz"])).status()
    assert missing["state"] == "not_installed" and missing["execution_mode"] == "manual_handoff"
    disabled = ClaudeCodeProvider(ProviderSettings(enabled=False, command=fake_cli["command"])).status()
    assert disabled["state"] == "disabled" and disabled["version"].startswith("9.9.9")
    enabled = AntigravityProvider(ProviderSettings(enabled=True, command=fake_cli["command"])).status()
    assert enabled["execution_mode"] == "supported_cli_task"


def test_ollama_url_must_be_local():
    with pytest.raises(ValueError):
        Settings(ollama_url="http://example.com:11434")
    assert Settings(ollama_url="http://localhost:11434/").ollama_url == "http://localhost:11434"


# ---------------------------------------------------------------- 공식 범위·보안

def test_sanitized_env_strips_paid_api_keys():
    env = sanitized_env({"PATH": "x", "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "b", "GOOGLE_API_KEY": "c",
                         "OPENAI_API_KEY": "d", "MY_SERVICE_API_TOKEN": "e", "ANTHROPIC_BASE_URL": "f"})
    assert env == {"PATH": "x"}


def test_cli_args_are_text_only_and_never_forbidden():
    cc = ClaudeCodeProvider().build_args(json_schema=None, model_id="sonnet")
    assert cc[:2] == ["-p", "--output-format"] and "--tools" in cc and cc[cc.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cc and "--strict-mcp-config" in cc
    ag = AntigravityProvider().build_args(json_schema={"type": "object"}, model_id=None)
    assert ag[ag.index("--mode") + 1] == "plan" and "--sandbox" in ag and "--json-schema" in ag
    for args in (cc, ag):
        assert not set(args) & set(FORBIDDEN_FLAGS)


def test_cli_subprocess_runs_in_empty_dir_without_api_keys(fake_cli):
    p = ClaudeCodeProvider(ProviderSettings(enabled=True, command=fake_cli["command"]))
    res = p.generate_text("PROMPT", system="SYS", json_schema=None, seed=None, model_id=None)
    log = json.loads(fake_cli["log"].read_text(encoding="utf-8"))
    assert "ANTHROPIC_API_KEY" not in log["env_keys"] and "GEMINI_API_KEY" not in log["env_keys"]
    assert log["cwd_files"] == []  # 프로젝트 파일에 접근할 수 없는 빈 폴더
    assert log["prompt"].startswith("SYS")
    assert res.tokens_in == 11 and res.tokens_out == 22
    assert "total_cost_usd" not in json.dumps(res.raw_meta)  # API 과금 필드 저장 안 함


def test_disabled_cli_never_executes(fake_cli):
    p = ClaudeCodeProvider(ProviderSettings(enabled=False, command=fake_cli["command"]))
    with pytest.raises(ProviderCallError) as e:
        p.generate_text("x", system="y", json_schema=None, seed=None, model_id=None)
    assert e.value.kind == "disabled" and not fake_cli["log"].exists()


def test_cli_rate_limit_detected(fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_CLI_MODE", "ratelimit")
    p = ClaudeCodeProvider(ProviderSettings(enabled=True, command=fake_cli["command"]))
    with pytest.raises(ProviderCallError) as e:
        p.generate_text("x", system="y", json_schema=None, seed=None, model_id=None)
    assert e.value.kind == "rate_limited"


# ---------------------------------------------------------------- 동의·전송 범위

def test_payload_excludes_sensitive_fields_and_rejects_unknown():
    payload = aig.build_payload(_req(liked_examples=["심지아"]), aig.DEFAULT_SEND)
    assert "surname_hangul" not in payload and set(payload) <= set(aig.SENDABLE_FIELDS)
    with pytest.raises(ValueError):
        aig.build_payload(_req(), ["birth_date"])


def test_external_provider_requires_consent(lexicon_session, fake_cli):
    lexicon_session.add(AIProviderSetting(provider_id="claude_code", enabled=True, command=fake_cli["command"]))
    lexicon_session.flush()
    with pytest.raises(aig.AIConsentRequired) as e:
        aig.run_ai_generation(lexicon_session, _req(), provider="claude_code", send_fields=None, consent=False,
                              ollama_url="http://127.0.0.1:9")
    assert e.value.preview["external"] and "출생일시" in e.value.preview["not_sent"]
    assert not fake_cli["log"].exists()  # 동의 전에는 실행 안 됨


# ---------------------------------------------------------------- 응답 검증

def test_validation_rejects_bad_ai_output(lexicon_session):
    doc = {"candidates": [
        {"given_hangul": "지아", "given_hanja": "智雅", "reason": "부드럽습니다"},
        {"given_hangul": "Jia"},                                     # 한글 아님
        {"given_hangul": "지아"},                                     # 중복
        {"given_hangul": "하나둘"},                                   # 음절 수
        {"given_hangul": "심수아"},                                   # 성 포함 → 보정
        {"given_hangul": "지수", "given_hanja": "智秀", "reason": "반드시 성공합니다"},  # 금지 표현 → 설명 제거
        {"given_hangul": "지우", "given_hanja": "金金"},             # 독음 불일치(AI 환각)
        {"given_hangul": "바보"},                                     # 비하 정확 일치
    ]}
    v = aig.validate_candidates(lexicon_session, doc, _req())
    acc = {a["given_hangul"]: a for a in v["accepted"]}
    assert set(acc) == {"지아", "수아", "지수"}
    assert acc["지수"]["reason"] is None and acc["지수"]["reason_removed_why"] == "forbidden_claim"
    assert acc["지아"]["reason"] == "부드럽습니다"
    reasons = {r["reason"] for r in v["rejected"]}
    assert {"not_hangul", "duplicate", "syllable_count", "hanja_reading_unverified", "caution_exact"} <= reasons


def test_ai_calculation_claims_are_stripped(lexicon_session):
    doc = {"candidates": [{"given_hangul": "하린", "reason": "사주에 물이 부족해 좋습니다"}]}
    a = aig.validate_candidates(lexicon_session, doc, _req())["accepted"][0]
    assert a["reason"] is None and a["reason_removed_why"] == "calculation_claim"


def test_parse_handles_fenced_json_and_rejects_extra_fields():
    assert aig.parse_ai_json('설명입니다\n```json\n{"candidates": []}\n```')["candidates"] == []
    with pytest.raises(Exception):
        aig.parse_ai_json('{"candidates": [{"given_hangul": "지아", "score": 100}]}')  # 점수 조작 필드 거부


# ---------------------------------------------------------------- 실행·폴백·기록

def test_no_model_falls_back_to_rule_based_and_records(lexicon_session, fake_ollama):
    f = fake_ollama([EMB])
    r = aig.run_ai_generation(lexicon_session, _req(), provider="ollama", send_fields=None, consent=False,
                              ollama_url=f.url)
    assert r.provider_used == "rule_based" and r.fallback_reason == "no_provider_available" and r.candidates
    assert r.attempts == [{"provider": "ollama", "result": "unavailable", "detail": "no_generation_model"}]
    rec = lexicon_session.get(AIGenerationRecord, r.record_id)
    assert rec.status == "fallback" and rec.provider_id == "rule_based"


def test_ollama_generation_validated_and_recorded(lexicon_session, fake_ollama):
    f = fake_ollama([GEN], chat_content=json.dumps({"candidates": [
        {"given_hangul": "지아", "given_hanja": "智雅", "reason": "부르기 편함"}, {"given_hangul": "X"}]}))
    r = aig.run_ai_generation(lexicon_session, _req(), provider="ollama", send_fields=None, consent=False, seed=42,
                              ollama_url=f.url)
    assert r.provider_used == "ollama" and [c["given_hangul"] for c in r.candidates] == ["지아"]
    path, body = [x for x in f.requests if x[0] == "/api/chat"][0]
    assert body["options"]["seed"] == 42 and body["format"] == aig.CANDIDATES_SCHEMA
    rec = lexicon_session.get(AIGenerationRecord, r.record_id)
    assert (rec.model_id, rec.prompt_version, rec.seed, rec.status) == ("gemma-fake", aig.PROMPT_VERSION, 42, "partial")
    inv = lexicon_session.query(AIInvocation).one()
    assert (inv.provider_id, inv.status, inv.tokens_in, inv.quota_data_status) == ("ollama", "success", 50,
                                                                                  "not_applicable")
    assert "심" not in json.dumps(body["messages"][1]["content"])  # 성씨는 기본 전송 안 함


def test_invalid_ai_json_falls_back(lexicon_session, fake_ollama):
    f = fake_ollama([GEN], chat_content="이름은 지아가 좋겠어요")
    r = aig.run_ai_generation(lexicon_session, _req(), provider="ollama", send_fields=None, consent=False,
                              ollama_url=f.url)
    assert r.provider_used == "rule_based"
    assert {"provider": "ollama", "result": "invalid_output"} in r.attempts


def test_cli_rate_limit_then_rule_based(lexicon_session, fake_cli, monkeypatch):
    monkeypatch.setenv("FAKE_CLI_MODE", "ratelimit")
    lexicon_session.add(AIProviderSetting(provider_id="claude_code", enabled=True, command=fake_cli["command"]))
    lexicon_session.flush()
    r = aig.run_ai_generation(lexicon_session, _req(), provider="claude_code", send_fields=None, consent=True,
                              ollama_url="http://127.0.0.1:9")
    assert r.provider_used == "rule_based" and {"provider": "claude_code", "result": "rate_limited"} in r.attempts


def test_auto_fallback_only_to_allowed_providers(lexicon_session, fake_cli, fake_ollama):
    f = fake_ollama([GEN], chat_content=json.dumps({"candidates": [{"given_hangul": "하린"}]}))
    lexicon_session.add_all([
        AIProviderSetting(provider_id="claude_code", enabled=True, command=fake_cli["command"], fallback_rank=1,
                          allow_auto_fallback=False),
        AIProviderSetting(provider_id="ollama", enabled=True, fallback_rank=2, allow_auto_fallback=True)])
    lexicon_session.flush()
    order = aig.fallback_order(lexicon_session, "antigravity")
    assert order == ["antigravity", "ollama"]  # claude_code 는 자동 대체 미허용
    r = aig.run_ai_generation(lexicon_session, _req(), provider="antigravity", send_fields=None, consent=True,
                              ollama_url=f.url)
    assert r.provider_used == "ollama"
    assert {"provider": "antigravity", "result": "disabled"} in r.attempts


def test_rule_based_when_ai_disabled_is_reproducible(lexicon_session):
    a = aig.run_ai_generation(lexicon_session, _req(), provider="none", send_fields=None, consent=False)
    b = aig.run_ai_generation(lexicon_session, _req(), provider="none", send_fields=None, consent=False)
    assert [c["given_hangul"] for c in a.candidates] == [c["given_hangul"] for c in b.candidates]
    assert a.fallback_reason is None


def test_mock_module_still_satisfies_protocols():
    for p in default_mock_providers():
        assert isinstance(p, AIProvider)
        assert isinstance(MockUsageCollector(p.id), UsageCollector)
    assert asyncio.run(MockUsageCollector("claude_code").collect()) == []
    assert isinstance(OllamaProvider(), AIProvider)


def test_disabled_ollama_is_never_called(lexicon_session, fake_ollama):
    f = fake_ollama([GEN], chat_content=json.dumps({"candidates": [{"given_hangul": "하린"}]}))
    lexicon_session.add(AIProviderSetting(provider_id="ollama", enabled=False))
    lexicon_session.flush()
    for provider in ("ollama", "auto"):
        r = aig.run_ai_generation(lexicon_session, _req(), provider=provider, send_fields=None, consent=False,
                                  ollama_url=f.url)
        assert r.provider_used == "rule_based"
    assert not [x for x in f.requests if x[0] == "/api/chat"]
    st = OllamaProvider(ProviderSettings(enabled=False, base_url=f.url)).status()
    assert st["state"] == "disabled" and st["reason"] == "disabled_by_user"


def test_disabled_external_provider_needs_no_consent_and_sends_nothing(lexicon_session, fake_cli):
    lexicon_session.add(AIProviderSetting(provider_id="claude_code", enabled=False, command=fake_cli["command"]))
    lexicon_session.flush()
    r = aig.run_ai_generation(lexicon_session, _req(), provider="claude_code", send_fields=None, consent=False,
                              ollama_url="http://127.0.0.1:9")
    assert r.provider_used == "rule_based" and {"provider": "claude_code", "result": "disabled"} in r.attempts
    assert not fake_cli["log"].exists()


def test_wsl_autodetect_builds_wsl_command(monkeypatch):
    from namecraft.ai_gateway import providers

    monkeypatch.setattr(providers.shutil, "which", lambda name: None)
    monkeypatch.setattr(providers, "wsl_lookup", lambda name: f"/home/u/.local/bin/{name}")
    p = ClaudeCodeProvider(ProviderSettings())
    assert p.resolved_command() == ["wsl.exe", "-e", "/home/u/.local/bin/claude"] and p.detected_via == "wsl"
    p2 = ClaudeCodeProvider(ProviderSettings(command=["mycli"]))
    assert p2.resolved_command() == ["mycli"] and p2.detected_via == "configured"  # 직접 지정이 우선


def test_live_connection_test(lexicon_client, fake_cli):
    c = lexicon_client
    r = c.post("/api/v1/ai/providers/claude_code/test?live=true").json()["data"]
    assert r["test_result"] in ("disabled",) or r["state"] == "not_installed"
    c.patch("/api/v1/ai/preferences", json={"provider_id": "claude_code", "enabled": True, "command": fake_cli["command"]})
    r = c.post("/api/v1/ai/providers/claude_code/test?live=true").json()
    assert r["data"]["test_result"] == "ok" and r["data"]["test_names"] == ["지우"]
    assert r["warnings"][0]["code"] == "live_test"
    log = json.loads(fake_cli["log"].read_text(encoding="utf-8"))
    assert "심" not in log["prompt"] and "birth" not in log["prompt"]  # 개인정보 없는 시험 요청
    sess = c.get("/api/v1/ai/sessions").json()["data"]
    assert sess[0]["execution_mode"] == "connection_test" and sess[0]["status"] == "success"
