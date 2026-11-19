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
