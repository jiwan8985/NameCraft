"""API 수준 E2E (기획서 §22.1 통합 / §32 Phase 8: 모델 선택→검증→추천 결과 흐름).

브라우저 E2E(Playwright)는 최종 테스트 단계에서 수행한다(D-022).
"""

import json

from namecraft.db.models import AIProviderSetting


def test_model_selection_to_recommendation_flow(lexicon_client, lexicon_session, fake_ollama):
    f = fake_ollama([{"name": "ko-fake", "caps": ["completion"]}], chat_content=json.dumps({"candidates": [
        {"given_hangul": "지아", "given_hanja": "智雅", "reason": "부르기 편한 이름"},
        {"given_hangul": "하린", "reason": "사주에 좋음"}, {"given_hangul": "Bad"}]}))
    lexicon_client.app.state.settings.ollama_url = f.url
    # 1) 모델 선택
    r = lexicon_client.patch("/api/v1/ai/preferences", json={"provider_id": "ollama", "enabled": True,
                                                              "model_id": "ko-fake"})
    assert r.status_code == 200
    prov = lexicon_client.get("/api/v1/ai/providers").json()["data"][0]
    assert prov["execution_mode"] == "native_local" and prov["selected_model"] == "ko-fake"
    # 2) 프로젝트 → AI 생성 → 서버 검증
    p = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "심", "surname_hanja": "沈", "sex": "f",
                                                      "preferences": {"name_type": "any", "count": 5}}).json()["data"]
    g = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate",
                            json={"provider": "ollama", "seed": 1}).json()["data"]
    assert g["provider_used"] == "ollama"
    saved = {c["given_hangul"]: c for c in g["saved"]}
    assert set(saved) == {"지아", "하린"} and saved["하린"]["ai_reason"] is None  # 계산 주장 설명 제거
    # 3) 추천 결과 — 모델·출처 표시
    items = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]
    assert all(i["source"] == "ai_based" for i in items)
    detail = lexicon_client.get(f"/api/v1/candidates/{saved['지아']['id']}").json()["data"]
    assert detail["generation"]["model_id"] == "ko-fake" and detail["generation"]["provider_id"] == "ollama"
    assert detail["generation"]["prompt_version"] and detail["generation"]["seed"] == 1
    # 4) 모든 점수 근거 조회 가능 (Phase 8 게이트)
    for cat in detail["ranking"]["categories"].values():
        assert cat["basis"] and cat["nature"] and "weight" in cat
    assert detail["explanation"]["source"] == "template"
    # 5) 반응 → 비교
    lexicon_client.post("/api/v1/reactions", json={"candidate_id": saved["지아"]["id"], "reaction": "like"})
    cmp = lexicon_client.post("/api/v1/names/compare", json={"surname_hangul": "심", "surname_hanja": "沈",
                                                             "names": [{"given_hangul": "지아", "given_hanja": "智雅"},
                                                                       {"given_hangul": "하린"}]}).json()
    assert len(cmp["data"]["items"]) == 2 and len(cmp["data"]["similarity"]) == 1


def test_ai_disabled_flow_still_works(lexicon_client, lexicon_session):
    lexicon_session.add(AIProviderSetting(provider_id="ollama", enabled=False))
    lexicon_session.commit()
    p = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "김", "preferences": {"name_type": "hangul",
                                                                                            "count": 4}}).json()["data"]
    g = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "auto"}).json()["data"]
    assert g["provider_used"] == "rule_based" and len(g["saved"]) == 4
    first = g["saved"][0]["id"]
    assert lexicon_client.get(f"/api/v1/candidates/{first}").status_code == 200
    assert lexicon_client.get("/api/v1/candidates/nope").status_code == 404
    bad = lexicon_client.post("/api/v1/names/compare", json={"surname_hangul": "김", "names": [{"given_hangul": "x"}]})
    assert bad.status_code == 422


def test_subscription_handoff_saves_valid_names_without_recording_unobserved_usage(lexicon_client):
    client = lexicon_client
    project = client.post("/api/v1/projects", json={
        "surname_hangul": "심", "constraints": {"include_syllables": ["아"], "fixed_syllable": {"1": "아"}},
    }).json()["data"]
    path = f"/api/v1/projects/{project['id']}/candidates/handoff"
    prompt = client.get(path).json()["data"]
    assert "한글 이름 | 한자 | 뜻" in prompt["prompt"] and "심" not in prompt["prompt"] and "2번째 글자" in prompt["prompt"]
    assert client.post(path, json={"provider": "claude_code", "pasted": "bad JSON"}).status_code == 400
    body = {"provider": "claude_code", "pasted": json.dumps({"candidates": [
        {"given_hangul": "지아", "reason": "부르기 편한 이름"}, {"given_hangul": "하린"},
    ]})}
    assert client.post(path, json=body).json()["data"]["saved"] == 1
    assert client.post(path, json={"provider": "claude_code", "pasted": "1. 지아, 하린"}).json()["data"]["saved"] == 0
    assert client.post(path, json={"provider": "antigravity", "pasted": "- 서아 | | 부드러운 이름"}).json()["data"]["saved"] == 1
    items = client.get(f"/api/v1/projects/{project['id']}/candidates").json()["data"]["items"]
    assert {(row["given_hangul"], row["source"], row["provider_id"]) for row in items} == {
        ("지아", "ai_based", "claude_code"), ("서아", "ai_based", "antigravity"),
    }
    assert client.get("/api/v1/ai/sessions").json()["data"] == []
    project_path = f"/api/v1/projects/{project['id']}"
    assert client.delete(project_path).status_code == 200
    assert client.get(project_path).status_code == 404


def test_click_to_use_local_ai_without_enabling_other_providers(lexicon_client, lexicon_session, fake_ollama):
    f = fake_ollama([{"name": "ko-fake", "caps": ["completion"]}],
                    chat_content='{"candidates":[{"given_hangul":"지아"}]}')
    lexicon_client.app.state.settings.ollama_url = f.url
    lexicon_session.add_all([
        AIProviderSetting(provider_id="ollama", enabled=False),
        AIProviderSetting(provider_id="claude_code", enabled=True, allow_auto_fallback=True),
    ])
    lexicon_session.commit()

    status = lexicon_client.get("/api/v1/ai/providers/ollama").json()["data"]
    assert status["execution_mode"] == "native_local" and status["models"][0]["can_generate"]
    project = lexicon_client.post("/api/v1/projects", json={"surname_hangul": "김"}).json()["data"]
    path = f"/api/v1/projects/{project['id']}/candidates/generate"
    response = lexicon_client.post(path, json={"provider": "ollama", "local_only": True})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider_used"] == "ollama"
    assert [candidate["given_hangul"] for candidate in data["saved"]] == ["지아"]
    assert lexicon_session.get(AIProviderSetting, "ollama").enabled is False


def test_ollama_recommendation_uses_memory_and_excludes_remote_models(lexicon_client, fake_ollama, monkeypatch):
    from namecraft.services import ollama_recommendation as rec

    f = fake_ollama([
        {"name": "qwen-coder", "caps": ["completion"], "size": 5 * rec.GIB},
        {"name": "phi4-mini", "caps": ["completion"], "size": 2 * rec.GIB},
        {"name": "embed", "caps": ["embedding"], "size": rec.GIB},
        {"name": "external:cloud", "caps": ["completion"], "size": rec.GIB},
    ])
    lexicon_client.app.state.settings.ollama_url = f.url
    monkeypatch.setattr(rec, "hardware_snapshot", lambda: {
        "logical_cpus": 16, "ram_available_bytes": 8 * rec.GIB, "ram_total_bytes": 32 * rec.GIB,
        "gpus": [{"available_bytes": 2 * rec.GIB}],
    })
    path = "/api/v1/ai/providers/ollama/recommendation"
    response = lexicon_client.get(path)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["recommended"] == "phi4-mini"
    assert [(m["name"], m["fit"]) for m in result["models"]] == [
        ("phi4-mini", "ram"), ("qwen-coder", "ram"),
    ]
    response = lexicon_client.patch("/api/v1/ai/preferences", json={
        "provider_id": "ollama", "model_id": result["recommended"],
    })
    assert response.status_code == 200
    assert lexicon_client.get(path).json()["data"]["selected_model"] == "phi4-mini"
