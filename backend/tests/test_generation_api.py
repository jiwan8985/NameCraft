def test_generate_endpoint(lexicon_client):
    b = lexicon_client.post("/api/v1/names/generate", json={
        "surname_hangul": "심", "surname_hanja": "沈", "sex": "f", "count": 5,
        "liked_examples": ["심지아"], "style_tags": {"soft": 1}}).json()
    assert b["status"] == "ok" and len(b["data"]["on_hold"]) == 5
    assert {"rule_based_generation", "official_gate_on_hold"} <= {w["code"] for w in b["warnings"]}


def test_generate_validation(lexicon_client):
    assert lexicon_client.post("/api/v1/names/generate", json={"surname_hangul": "심", "syllables": 5}).status_code == 422
    assert lexicon_client.post("/api/v1/names/generate", json={"surname_hangul": "심", "sex": "x"}).status_code == 422
    r = lexicon_client.post("/api/v1/names/generate", json={"surname_hangul": "Sim"})
    assert r.status_code == 400


def test_reverse_search_and_alternatives_endpoints(lexicon_client):
    b = lexicon_client.post("/api/v1/names/reverse-search", json={"given_hangul": "지아", "surname_hanja": "沈",
                                                                  "limit": 5}).json()
    assert len(b["data"]["combinations"]["on_hold"]) == 5 and b["verification_status"] == "unverified"
    r = lexicon_client.post("/api/v1/names/reverse-search", json={"given_hangul": "지아", "weights": {"luck81": -1}})
    assert r.status_code == 400
    a = lexicon_client.post("/api/v1/names/alternative-hanja", json={
        "given_hangul": "지아", "given_hanja": "智雅", "surname_hanja": "沈"}).json()
    assert len(a["data"]["positions"]) == 2
    bad = lexicon_client.post("/api/v1/names/alternative-hanja", json={"given_hangul": "지아", "given_hanja": "金雅"})
    assert bad.status_code == 400
