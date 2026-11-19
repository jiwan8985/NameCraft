"""프로젝트·후보·반응·랭킹·취향 학습 (REQ-RK-001~005, REQ-AI-001/002, 수용 기준 §23)."""

from __future__ import annotations

import pytest

from namecraft.services.ranking import DEFAULT_WEIGHTS, RankingError, normalize_weights, preference_score, \
    preference_profile


def _project(c, **kw):
    body = {"surname_hangul": "심", "surname_hanja": "沈", "sex": "f",
            "preferences": {"name_type": "any", "count": 8, "liked_examples": ["심지아"]}, **kw}
    r = c.post("/api/v1/projects", json=body)
    assert r.status_code == 201
    return r.json()["data"]


def test_weights_normalized_and_validated():
    w = normalize_weights(None)
    assert abs(sum(w.values()) - 1) < 1e-9 and w["phonetic"] == 0.25
    assert normalize_weights({"phonetic": 50, "meaning": 0, "saju": 0, "numerology": 0, "usability": 0,
                              "preference": 0})["phonetic"] == 1.0
    for bad in ({"phonetic": -1}, {k: 0 for k in DEFAULT_WEIGHTS}, {"luck": 10}):
        with pytest.raises(RankingError):
            normalize_weights(bad)


def test_preference_learning_moves_scores():
    assert preference_score("지아", preference_profile([], [])) is None
    prof = preference_profile(["지아", "하은"], ["강철"])
    assert preference_score("지안", prof) > preference_score("강혁", prof)


def test_project_crud_and_generation_saves_candidates(lexicon_client):
    p = _project(lexicon_client)
    assert lexicon_client.get(f"/api/v1/projects/{p['id']}").json()["data"]["surname_hanja"] == "沈"
    patched = lexicon_client.patch(f"/api/v1/projects/{p['id']}", json={"preferences": {"style_tags": {"soft": 1}}})
    assert patched.json()["data"]["preferences"]["style_tags"] == {"soft": 1}
    g = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "none"}).json()
    assert g["data"]["provider_used"] == "rule_based" and len(g["data"]["saved"]) == 8
    # 다시 생성해도 이미 저장된 후보를 또 만들지 않음
    g2 = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "none"}).json()
    first = {c["given_hangul"] for c in g["data"]["saved"]}
    assert not first & {c["given_hangul"] for c in g2["data"]["saved"]}
    assert lexicon_client.get("/api/v1/projects").json()["data"][0]["id"] == p["id"]


def test_ranking_structure_gate_and_na(lexicon_client):
    p = _project(lexicon_client)
    lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "지아", "given_hanja": "智雅"})
    lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "초롱"})
    b = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()
    items = {i["given_hangul"]: i for i in b["data"]["items"]}
    jia, chorong = items["지아"], items["초롱"]
    assert jia["gate"]["official_hanja"] == "unknown" and chorong["gate"]["official_hanja"] == "pass"
    assert jia["categories"]["saju"]["score"] is None and "saju" in jia["incomplete"]  # 0점 대체 금지
    assert chorong["categories"]["numerology"]["score"] is None and "numerology" in chorong["incomplete"]
    eff = sum(c["effective_weight"] for c in jia["categories"].values())
    assert abs(eff - 1) < 1e-3
    assert {"incomplete_data", "official_gate_unknown"} <= {w["code"] for w in b["warnings"]}
    assert jia["confidence"]["reproducible"] is True and jia["confidence"]["data_verification"] == "unverified"


def test_sort_views(lexicon_client):
    p = _project(lexicon_client)
    for n in ("지아", "하은", "초롱"):
        lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": n})
    for view in ("overall", "phonetic", "usability", "numerology"):
        items = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates", params={"sort": view}).json()["data"]["items"]
        key = (lambda i: i["overall"]) if view == "overall" else (lambda i: i["categories"][view]["score"])
        vals = [key(i) for i in items if key(i) is not None]
        assert vals == sorted(vals, reverse=True)
    assert lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates", params={"sort": "luck"}).status_code == 400


def test_reactions_exclude_and_restore(lexicon_client):
    p = _project(lexicon_client)
    c = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "강철"}).json()["data"]
    keep = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "지아"}).json()["data"]
    r = lexicon_client.post("/api/v1/reactions", json={"candidate_id": c["id"], "reaction": "dislike",
                                                       "reasons": ["too_strong"], "memo": "느낌이 강함"})
    assert r.status_code == 201 and r.json()["data"]["candidate"]["status"] == "excluded"
    listed = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]
    assert [i["given_hangul"] for i in listed] == ["지아"]
    # 싫어요 한 이름은 새 생성에서 제외 (REQ-AI-002)
    g = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates/generate", json={"provider": "none", "count": 30})
    assert "강철" not in {s["given_hangul"] for s in g.json()["data"]["saved"]}
    # 해제
    lexicon_client.patch(f"/api/v1/candidates/{c['id']}", json={"status": "active"})
    all_items = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]
    assert "강철" in {i["given_hangul"] for i in all_items}
    # 좋아요 → 취향 점수 반영
    lexicon_client.post("/api/v1/reactions", json={"candidate_id": keep["id"], "reaction": "like"})
    items = {i["given_hangul"]: i for i in
             lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]}
    assert items["지아"]["reaction"] == "like" and items["지아"]["categories"]["preference"]["score"] is not None


def test_candidate_validation_and_duplicates(lexicon_client):
    p = _project(lexicon_client)
    assert lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "Jia"}).status_code == 400
    lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "지아"})
    dup = lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "지아"})
    assert dup.status_code == 400 and dup.json()["error"]["details"]["duplicate"]
    assert lexicon_client.get("/api/v1/projects/nope").status_code == 404
    assert lexicon_client.post("/api/v1/reactions", json={"candidate_id": "nope", "reaction": "like"}).status_code == 404


def test_ai_router(lexicon_client, fake_cli):
    prov = lexicon_client.get("/api/v1/ai/providers").json()["data"]
    assert [p["provider_id"] for p in prov] == ["ollama", "claude_code", "antigravity"]
    assert prov[0]["state"] == "not_installed"  # 테스트는 닫힌 포트 사용
    assert all(p["is_mock"] is False for p in prov)
    bad = lexicon_client.patch("/api/v1/ai/preferences", json={"provider_id": "claude_code", "command": ["claude", "--bare"]})
    assert bad.status_code == 400
    ok = lexicon_client.patch("/api/v1/ai/preferences", json={"provider_id": "claude_code", "enabled": True,
                                                               "command": fake_cli["command"]})
    assert ok.json()["data"]["enabled"] is True
    st = lexicon_client.post("/api/v1/ai/providers/claude_code/test").json()["data"]
    assert st["test_result"] == "status_only" and st["execution_mode"] == "supported_cli_task"
    assert not fake_cli["log"].exists()  # 상태 확인은 생성 호출을 하지 않음
    need = lexicon_client.post("/api/v1/ai/generate", json={"provider": "claude_code", "surname_hangul": "심"})
    assert need.status_code == 400 and need.json()["error"]["details"]["consent_required"]
    dry = lexicon_client.post("/api/v1/ai/generate", json={"provider": "claude_code", "surname_hangul": "심",
                                                           "dry_run": True}).json()["data"]["preview"]
    assert dry["external"] and {f["key"] for f in dry["fields"]} == set(["sex", "syllables", "style_tags",
                                                                         "liked_examples", "count"])
    gen = lexicon_client.post("/api/v1/ai/generate", json={"provider": "claude_code", "surname_hangul": "심",
                                                           "consent": True}).json()
    assert gen["data"]["provider_used"] == "claude_code"
    assert [c["given_hangul"] for c in gen["data"]["candidates"]] == ["지우"]


def test_manual_handoff_roundtrip(lexicon_client):
    pr = lexicon_client.post("/api/v1/ai/handoff/prompt", json={"provider": "antigravity", "surname_hangul": "심",
                                                                 "liked_examples": ["심지아"]}).json()["data"]
    assert "candidates" in pr["system"] and pr["expected_schema"]["required"] == ["candidates"]
    imp = lexicon_client.post("/api/v1/ai/handoff/import", json={
        "provider": "antigravity", "surname_hangul": "심",
        "pasted": '```json\n{"candidates":[{"given_hangul":"하린"},{"given_hangul":"Xx"}]}\n```'}).json()["data"]
    assert [a["given_hangul"] for a in imp["accepted"]] == ["하린"] and imp["rejected"][0]["reason"] == "not_hangul"
    bad = lexicon_client.post("/api/v1/ai/handoff/import", json={"provider": "antigravity", "surname_hangul": "심",
                                                                  "pasted": "그냥 텍스트"})
    assert bad.status_code == 400
