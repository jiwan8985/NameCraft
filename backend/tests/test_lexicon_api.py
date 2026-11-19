"""Phase 2 조회 API: GET /surnames, GET /hanja, 임시 성씨, 데이터 관리."""

from __future__ import annotations

from namecraft.adapters.importers.scourt_hanja import import_official_csv

from conftest import SCOURT_SAMPLE


def test_surname_homophones_listed(lexicon_client):
    body = lexicon_client.get("/api/v1/surnames", params={"q": "정"}).json()
    assert {i["hanja"] for i in body["data"]} == {"鄭", "丁", "程"}
    assert body["verification_status"] == "unverified"
    assert body["warnings"][0]["code"] == "surname_seed_unverified"


def test_surname_by_initial_sound_variant_and_compound(lexicon_client):
    lee = lexicon_client.get("/api/v1/surnames", params={"q": "리"}).json()["data"]
    assert [i["hanja"] for i in lee] == ["李"] and "리" in lee[0]["alt_hangul"]
    ng = lexicon_client.get("/api/v1/surnames", params={"q": "남궁"}).json()["data"][0]
    assert ng["is_compound"] and [c["modern_strokes"] for c in ng["characters"]] == [9, 10]
    assert [c["original_strokes"] for c in ng["characters"]] == [9, 10]


def test_unknown_surname_and_provisional_record(lexicon_client):
    assert lexicon_client.get("/api/v1/surnames", params={"q": "뷁"}).json()["warnings"][0]["code"] == "surname_not_found"
    r = lexicon_client.post("/api/v1/surnames/provisional", json={"hangul": "뷁"})
    assert r.status_code == 201 and r.json()["data"]["is_provisional"] is True
    found = lexicon_client.get("/api/v1/surnames", params={"q": "뷁"}).json()["data"]
    assert found[0]["record_status"] == "unverified" and found[0]["source_id"] == "SRC-USER-INPUT"
    bad = lexicon_client.post("/api/v1/surnames/provisional", json={"hangul": "김", "hanja": "金李"})
    assert bad.status_code == 400


def test_hanja_reverse_search_by_reading(lexicon_client):
    body = lexicon_client.get("/api/v1/hanja", params={"reading": "심", "name_only": True}).json()
    cps = [i["codepoint"] for i in body["data"]]
    assert "U+6C88" in cps
    assert {w["code"] for w in body["warnings"]} == {"official_data_missing"}
    shim = next(i for i in body["data"] if i["codepoint"] == "U+6C88")
    assert shim["official"]["status"] == "unknown" and shim["official"]["requires_official_recheck"]
    assert {"system": "modern", "strokes": 7, "rule_id": "STROKE.MODERN.UNIHAN.v1",
            "profile_id": None, "source_id": "SRC-UNIHAN", "status": "unverified"} in shim["strokes"]
    assert any(p["source_id"] == "SRC-UNIHAN" and p["license"] == "Unicode License v3" for p in body["provenance"])


def test_hanja_char_lookup_returns_compat_family(lexicon_client):
    data = lexicon_client.get("/api/v1/hanja", params={"char": "李"}).json()["data"]
    assert {i["codepoint"] for i in data} == {"U+674E", "U+F9E1"}
    compat = next(i for i in data if i["codepoint"] == "U+F9E1")
    assert compat["is_compatibility"] and compat["char"] == "李"  # 접히지 않음


def test_hanja_detail_and_not_found(lexicon_client):
    d = lexicon_client.get("/api/v1/hanja/u+6a02").json()["data"]
    assert d["char"] == "樂" and len(d["readings"]) == 4
    assert lexicon_client.get("/api/v1/hanja/U+0041").status_code == 404
    assert lexicon_client.get("/api/v1/hanja").status_code == 400


def test_sample_official_data_is_not_verification(lexicon_client, lexicon_session):
    import_official_csv(lexicon_session, SCOURT_SAMPLE, is_sample=True)
    lexicon_session.commit()
    body = lexicon_client.get("/api/v1/hanja", params={"char": "沈"}).json()
    shim = next(i for i in body["data"] if i["codepoint"] == "U+6C88")
    assert shim["official"]["status"] == "sample_only"
    assert body["verification_status"] == "unverified"


def test_real_official_data_verifies_and_flags_unlisted(lexicon_client, lexicon_session, tmp_path):
    f = tmp_path / "official.csv"
    f.write_text("hanja,reading,effective_date,legal_basis\n沈,심,2024-01-01,TEST\n", encoding="utf-8")
    import_official_csv(lexicon_session, f, is_sample=False)
    lexicon_session.commit()
    shim = lexicon_client.get("/api/v1/hanja/U+6C88").json()
    assert shim["data"]["official"]["status"] == "verified" and shim["verification_status"] == "verified"
    assert shim["warnings"] == []
    gold = lexicon_client.get("/api/v1/hanja/U+91D1").json()
    assert gold["data"]["official"]["status"] == "not_listed" and gold["verification_status"] == "unverified"


def test_admin_data_summary(lexicon_client):
    d = lexicon_client.get("/api/v1/admin/data").json()["data"]
    assert d["summary"]["hanja_characters"] > 100 and d["summary"]["official_rules"] == 0
    assert d["summary"]["original_stroke_counts"] > 100
    assert any(r["id"].startswith("unihan-18.0.0") for r in d["releases"])
    assert any(s["id"] == "SRC-SCOURT-HANJA" and s["status"] == "license_review" for s in d["sources"])


def test_lexicon_routes_require_auth(client):
    assert client.get("/api/v1/hanja", params={"reading": "심"}).status_code == 401
    assert client.get("/api/v1/admin/data").status_code == 401
