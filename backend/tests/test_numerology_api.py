"""POST /numerology/calculate."""

from __future__ import annotations


def _post(c, **body):
    return c.post("/api/v1/numerology/calculate", json=body)


def test_full_analysis_separates_calc_and_trad(lexicon_client):
    b = _post(lexicon_client, surname_hangul="심", surname_hanja="沈", given_hangul="지아", given_hanja="智雅").json()
    assert b["verification_status"] == "traditional_interpretation"
    assert {"traditional_interpretation", "source_check_pending", "stroke_unverified"} <= {w["code"] for w in b["warnings"]}
    d = b["data"]
    assert d["calc"]["four_gyeok"]["won"] == {"value": 24, "reduced": 24, "element": "火"}
    assert d["trad"]["status"] == "source_check_pending"
    assert set(d["trad"]["luck81"]) == {"won", "hyeong", "i", "jeong"}
    assert sum(d["trad"]["luck81_counts"].values()) == 4
    assert d["calc"]["yinyang_pattern"] == ["음", "음", "음"] and d["trad"]["yinyang"]["value"] == "편중"
    shim = d["characters"][0]
    assert shim["original_strokes"] == 8 and shim["modern_strokes"] == 7 and "水" in shim["notes"][0]
    assert d["trad"]["jawon"]["elements"][0] == "水"  # 沈: 水 부수
    assert d["eumryeong"]["by_school"]["hunmin-haerye"]["elements"] == ["金", "金", "水"]
    assert d["eumryeong"]["school_agreement"] == {"agree_count": 2, "total": 3,
                                                  "note": "학파 간 일치도는 정확성의 증거가 아닙니다."}


def test_hangul_only_name_is_not_applicable(lexicon_client):
    b = _post(lexicon_client, surname_hangul="심", surname_hanja="沈", given_hangul="초롱").json()
    assert b["verification_status"] == "not_applicable"
    assert b["data"]["applicability"]["numerology"] == "not_applicable"
    assert "calc" not in b["data"]


def test_unknown_hanja_yields_unknown_not_zero(lexicon_client):
    b = _post(lexicon_client, surname_hangul="심", surname_hanja="沈", given_hangul="가", given_hanja="嘉").json()
    assert b["data"]["applicability"]["numerology"] == "unknown"
    assert "calc" not in b["data"]


def test_input_validation(lexicon_client):
    r = _post(lexicon_client, surname_hangul="심", surname_hanja="沈", given_hangul="지아", given_hanja="智")
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
    r = _post(lexicon_client, surname_hangul="심", given_hangul="지아", options={"stroke_system": "magic"})
    assert r.status_code == 422


def test_hanja_api_now_has_original_strokes(lexicon_client):
    d = lexicon_client.get("/api/v1/hanja/U+6C88").json()["data"]
    systems = {s["system"]: s for s in d["strokes"]}
    assert systems["modern"]["strokes"] == 7
    assert systems["original"]["strokes"] == 8 and systems["original"]["rule_id"] == "STROKE.ORIGINAL.v1"
