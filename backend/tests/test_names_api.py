"""POST /names/analyze, POST /names/similarity."""


def test_analyze_full_name_with_hanja(lexicon_client):
    b = lexicon_client.post("/api/v1/names/analyze", json={
        "surname_hangul": "심", "surname_hanja": "沈", "given_hangul": "지아", "given_hanja": "智雅"}).json()
    d = b["data"]
    assert d["name"]["full_hanja"] == "沈智雅"
    assert d["phonetics"]["pronunciation"]["pronounced"] == "심지아"
    assert d["romanization"]["given_rr"] == "Ji-a"
    assert d["numerology"]["calc"]["four_gyeok"]["jeong"]["value"] == 32
    assert d["meaning"]["characters"][0]["hanja"] == "智"
    codes = {w["code"] for w in b["warnings"]}
    assert {"traditional_interpretation", "korean_meaning_unavailable"} <= codes
    assert "caution_candidates" not in codes


def test_analyze_hangul_only_name(lexicon_client):
    b = lexicon_client.post("/api/v1/names/analyze", json={
        "surname_hangul": "심", "surname_hanja": "沈", "given_hangul": "초롱"}).json()
    d = b["data"]
    assert d["meaning"]["status"] == "not_applicable"
    assert d["numerology"]["applicability"]["numerology"] == "not_applicable"
    assert "traditional_interpretation" not in {w["code"] for w in b["warnings"]}
    assert any(n["code"] == "childlike_syllable" for n in d["usability"]["notes"])


def test_analyze_flags_caution(lexicon_client):
    b = lexicon_client.post("/api/v1/names/analyze", json={"surname_hangul": "김", "given_hangul": "똥이"}).json()
    assert "caution_candidates" in {w["code"] for w in b["warnings"]}


def test_analyze_validation(lexicon_client):
    r = lexicon_client.post("/api/v1/names/analyze", json={"surname_hangul": "심", "given_hangul": "Jia"})
    assert r.status_code == 400


def test_similarity_endpoint(lexicon_client):
    b = lexicon_client.post("/api/v1/names/similarity", json={"names": [
        {"given_hangul": "지아"}, {"given_hangul": "지안"}, {"given_hangul": "지아"}]}).json()
    pairs = {(p["a"], p["b"]): p for p in b["data"]}
    assert pairs[(0, 2)]["is_duplicate"] and not pairs[(0, 1)]["is_duplicate"]
    r = lexicon_client.post("/api/v1/names/similarity", json={"names": [{"given_hangul": "지아"}, {"x": 1}]})
    assert r.status_code == 400
