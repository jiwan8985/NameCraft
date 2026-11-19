"""POST /saju/calculate, GET /calendar/solar-terms."""

from __future__ import annotations

import logging


def test_exact_time_chart(client, auth):
    r = client.post("/api/v1/saju/calculate", headers=auth,
                    json={"date": "2027-01-15", "time": "10:00"})
    assert r.status_code == 200
    b = r.json()
    assert b["verification_status"] == "calculated"
    assert b["rule_profile"] == "kr-common-2026" and b["rule_version"] == "0.1.0-draft"
    assert {w["code"] for w in b["warnings"]} == {"draft_profile", "external_verification_pending"}
    assert any("입춘" in a for a in b["calculation_assumptions"])
    seg = b["data"]["segments"][0]
    assert seg["text"] == "丙午 辛丑 甲午 己巳" and seg["day_master"] == "甲"
    assert sum(seg["element_counts"].values()) == 8
    assert {p["source_id"] for p in b["provenance"]} == {"SRC-JPL-DE", "SRC-KLC-LIB"}


def test_time_range_returns_scenarios_not_average(client, auth):
    b = client.post("/api/v1/saju/calculate", headers=auth,
                    json={"date": "2027-01-15", "time_range": ["09:00", "12:00"], "longitude": 126.978,
                          "options": {"true_solar_time": "longitude_only"}}).json()
    assert len(b["data"]["segments"]) == 3
    assert "multiple_scenarios" in {w["code"] for w in b["warnings"]}


def test_unknown_time_without_hour_or_range(client, auth):
    b = client.post("/api/v1/saju/calculate", headers=auth, json={"date": "2027-01-15"}).json()
    assert b["data"]["mode"] == "time_unknown" and len(b["data"]["segments"]) == 13


def test_lunar_leap_input(client, auth):
    b = client.post("/api/v1/saju/calculate", headers=auth,
                    json={"calendar": "lunar", "date": "2023-02-01", "is_leap_month": True, "time": "12:00"}).json()
    assert b["data"]["input"]["solar_date"] == "2023-03-22"
    assert b["data"]["input"]["lunar_date"]["is_leap_month"] is True


def test_errors_are_structured_and_do_not_echo_input(client, auth):
    r = client.post("/api/v1/saju/calculate", headers=auth,
                    json={"calendar": "lunar", "date": "2024-03-01", "is_leap_month": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "calendar_input_invalid"
    r = client.post("/api/v1/saju/calculate", headers=auth, json={"date": "1899-12-31", "time": "12:00"})
    assert r.json()["error"]["code"] == "out_of_supported_range"
    r = client.post("/api/v1/saju/calculate", headers=auth, json={"date": "2027-13-45"})
    assert r.status_code == 422 and "2027-13-45" not in r.text
    r = client.post("/api/v1/saju/calculate", headers=auth,
                    json={"date": "2027-01-15", "options": {"true_solar_time": "longitude_only"}})
    assert r.json()["error"]["code"] == "calendar_input_invalid"  # 경도 누락
    r = client.post("/api/v1/saju/calculate", headers=auth, json={"date": "2027-01-15", "tz": "Mars/Base"})
    assert r.json()["error"]["code"] == "calendar_input_invalid"


def test_birth_data_not_logged(client, auth, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/api/v1/saju/calculate", headers=auth, json={"date": "2027-01-15", "time": "10:00"})
    assert "2027-01-15" not in caplog.text and "10:00" not in caplog.text


def test_solar_terms_endpoint(client, auth):
    b = client.get("/api/v1/calendar/solar-terms", params={"year": 2027}, headers=auth).json()
    assert len(b["data"]) == 24
    ipchun = next(t for t in b["data"] if t["hangul"] == "입춘")
    assert ipchun["local"].startswith("2027-02-04T10:46")
    assert client.get("/api/v1/calendar/solar-terms", params={"year": 2051}, headers=auth).status_code == 422


def test_saju_requires_auth(client):
    assert client.post("/api/v1/saju/calculate", json={"date": "2027-01-15"}).status_code == 401
