"""Phase 11 게이트: 데이터 왕복 · 보고서 · 실제/추정/미지원 구분 (기획서 §19, §30, §33)."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta

from namecraft.db.models import AIInvocation


def _project_with_everything(c):
    p = c.post("/api/v1/projects", json={"title": "왕복", "surname_hangul": "심", "surname_hanja": "沈", "sex": "f",
                                         "preferences": {"use_saju": True}}).json()["data"]
    ids = [c.post(f"/api/v1/projects/{p['id']}/candidates", json=j).json()["data"]["id"] for j in (
        {"given_hangul": "지아", "given_hanja": "智雅"}, {"given_hangul": "수림", "given_hanja": "秀林"}, {"given_hangul": "하은"})]
    c.post("/api/v1/reactions", json={"candidate_id": ids[0], "reaction": "like", "memo": "좋음"})
    c.post("/api/v1/reactions", json={"candidate_id": ids[2], "reaction": "dislike"})
    c.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={"date": "2027-01-15", "time_range": ["09:00", "12:00"], "day_window": 1})
    c.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={"kind": "actual", "date": "2027-01-16", "time": "10:42"})
    mom = c.post(f"/api/v1/projects/{p['id']}/members", json={"alias": "엄마"}).json()["data"]["id"]
    c.post("/api/v1/family/votes", json={"member_id": mom, "candidate_id": ids[1], "reaction": "like", "rank": 1})
    t = c.post("/api/v1/tournaments", json={"project_id": p["id"], "candidate_ids": ids[:2]}).json()["data"]
    c.post(f"/api/v1/tournaments/{t['id']}/vote", json={"match_index": 0, "choice": "a"})
    c.put(f"/api/v1/projects/{p['id']}/finalists", json={"candidate_ids": ids})
    c.post(f"/api/v1/projects/{p['id']}/decision", json={"candidate_id": ids[0], "reason": "가족 모두 좋아함"})
    c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "project_summary"})
    return p, ids


def _comparable(items):
    return sorted((i["given_hangul"], i["given_hanja"], i["overall"], i["status"], i["reaction"],
                   tuple(sorted((k, v["score"]) for k, v in i["categories"].items()))) for i in items)


def test_backup_roundtrip_reproduces_results(lexicon_client):
    """수용 기준 §23: 백업한 프로젝트를 복원해 비교·보고서 결과를 재현."""
    c = lexicon_client
    p, _ = _project_with_everything(c)
    exported = c.get(f"/api/v1/projects/{p['id']}/export")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    doc = exported.json()
    assert doc["schema"] == "namecraft.project" and len(doc["checksum_sha256"]) == 64
    assert c.post("/api/v1/backup/verify", json=doc).json()["data"] == {"ok": True, "problems": []}
    r = c.post("/api/v1/projects/import", json=doc)
    assert r.status_code == 201
    q = r.json()["data"]
    assert q["id"] != p["id"] and q["title"] == "왕복 (복원)"
    orig = c.get(f"/api/v1/projects/{p['id']}/candidates?include_excluded=true").json()["data"]["items"]
    rest = c.get(f"/api/v1/projects/{q['id']}/candidates?include_excluded=true").json()["data"]["items"]
    assert _comparable(orig) == _comparable(rest)  # 랭킹·사주 해석·반응 모두 동일
    hist = c.get(f"/api/v1/projects/{q['id']}/birth-profiles").json()["data"]
    assert [h["kind"] for h in hist] == ["expected", "actual"] and hist[0]["snapshots"]
    fam = c.get(f"/api/v1/projects/{q['id']}/family").json()["data"]
    assert fam["members"][0]["alias"] == "엄마" and fam["candidates"][0]["given_hangul"] == "수림"
    dec = c.get(f"/api/v1/projects/{q['id']}/decisions").json()["data"]
    names = {i["id"]: i["given_hangul"] for i in rest}
    assert names[dec[0]["chosen_candidate_id"]] == "지아" and dec[0]["reason"] == "가족 모두 좋아함"
    tours = c.get(f"/api/v1/projects/{q['id']}/tournaments").json()["data"]
    assert tours[0]["result"]["winner_name"].startswith("지아")
    assert c.get(f"/api/v1/projects/{q['id']}/reports").json()["data"][0]["kind"] == "project_summary"
    # 복원본에서 다시 생성한 보고서의 순위가 원본과 같음
    r1 = c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "project_summary"}).json()["data"]["snapshot"]
    r2 = c.post("/api/v1/reports", json={"project_id": q["id"], "kind": "project_summary"}).json()["data"]["snapshot"]
    assert [i["full_hangul"] for i in r1["ranking"]["items"]] == [i["full_hangul"] for i in r2["ranking"]["items"]]


def test_tampered_backup_rejected(lexicon_client):
    p, _ = _project_with_everything(lexicon_client)
    doc = lexicon_client.get(f"/api/v1/projects/{p['id']}/export").json()
    doc["data"]["candidates"][0]["given_hangul"] = "변조"
    v = lexicon_client.post("/api/v1/backup/verify", json=doc).json()["data"]
    assert v == {"ok": False, "problems": ["checksum"]}
    assert lexicon_client.post("/api/v1/projects/import", json=doc).status_code == 400
    assert lexicon_client.post("/api/v1/projects/import", json={"schema": "x"}).status_code == 400


def test_full_backup_and_restore_all_or_nothing(lexicon_client):
    _project_with_everything(lexicon_client)
    full = lexicon_client.get("/api/v1/backup").json()
    assert full["schema"] == "namecraft.backup" and len(full["projects"]) == 1
    bad = json.loads(json.dumps(full))
    bad["projects"][0]["checksum_sha256"] = "0" * 64
    before = len(lexicon_client.get("/api/v1/projects").json()["data"])
    assert lexicon_client.post("/api/v1/backup/restore", json=bad).status_code == 400
    assert len(lexicon_client.get("/api/v1/projects").json()["data"]) == before
    ok = lexicon_client.post("/api/v1/backup/restore", json=full).json()["data"]
    assert len(ok["restored_projects"]) == 1


def test_delete_project_and_all_data(lexicon_client, migrated_settings):
    c = lexicon_client
    p, _ = _project_with_everything(c)
    c.post("/api/v1/imports", files={"file": ("r.txt", io.BytesIO("원격 24".encode()), "text/plain")},
           data={"project_id": p["id"]})
    assert len(list((migrated_settings.var_dir / "uploads").iterdir())) == 1
    r = c.delete(f"/api/v1/projects/{p['id']}").json()["data"]
    assert r["deleted_documents"] == 1 and r["deleted_candidates"] == 3
    assert list((migrated_settings.var_dir / "uploads").iterdir()) == []
    assert c.get(f"/api/v1/projects/{p['id']}").status_code == 404
    _project_with_everything(c)
    assert c.post("/api/v1/data/delete-all", json={"confirm": "yes"}).status_code == 400
    w = c.post("/api/v1/data/delete-all", json={"confirm": "DELETE ALL"}).json()
    assert w["data"]["deleted_projects"] == 1 and c.get("/api/v1/projects").json()["data"] == []
    assert c.get("/api/v1/hanja/U+6C88").status_code == 200  # 참조 데이터는 유지


def test_reports_include_required_metadata_and_persist(lexicon_client):
    c = lexicon_client
    p, ids = _project_with_everything(c)
    rep = c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "project_summary"}).json()["data"]
    s = rep["snapshot"]
    assert s["conditions"]["birth"]["kind_label"] == "확정"
    assert s["conditions"]["school_options"]["stroke_system"] == "original"
    assert s["official_basis"]["official_data_loaded"] is False
    assert {"ranking", "numerology_rule", "calendar_engine", "data_releases"} <= set(rep["versions"])
    assert any("과학적 근거가 없습니다" in x for x in s["limitations"])
    assert s["decision"]["name"] == "심지아" and s["finalize_check"]["never_final"]
    again = c.get(f"/api/v1/reports/{rep['id']}").json()["data"]
    assert again["snapshot"] == s  # 다시 열면 당시 데이터 그대로
    d = c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "name_detail", "candidate_ids": [ids[0]]})
    assert d.status_code == 201 and d.json()["data"]["snapshot"]["detail"]["analysis"]["name"]["full_hangul"] == "심지아"
    cmp = c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "comparison", "candidate_ids": ids[:2]})
    assert len(cmp.json()["data"]["snapshot"]["comparison"]["items"]) == 2
    assert c.post("/api/v1/reports", json={"project_id": p["id"], "kind": "comparison", "candidate_ids": ["x", "y"]}).status_code == 400


def test_candidates_csv(lexicon_client):
    p, _ = _project_with_everything(lexicon_client)
    r = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates.csv")
    text = r.content.decode("utf-8")
    assert text.startswith("﻿순위,이름,한자,종합") and "심지아" in text and "N/A" in text
    assert "심하은" not in text  # 싫어요(제외)한 후보는 목록에서 빠짐


# ---------------------------------------------------------------- AI Usage Center

def test_usage_summary_never_sums_and_marks_sources(lexicon_client, lexicon_session):
    lexicon_session.add_all([
        AIInvocation(provider_id="ollama", execution_mode="native_local", model_id="m", task="generate_candidates",
                     status="success", duration_ms=1000, tokens_in=10, tokens_out=20),
        AIInvocation(provider_id="claude_code", execution_mode="supported_cli_task", model_id=None, task="generate_candidates",
                     status="error", duration_ms=None)])
    lexicon_session.commit()
    b = lexicon_client.get("/api/v1/ai/usage/summary").json()
    d = b["data"]
    assert "total" not in json.dumps(d).lower()
    cards = {x["provider_id"]: x for x in d["providers"]}
    assert cards["ollama"]["quota"]["status"] == "not_applicable" and "한도 없음" in cards["ollama"]["quota"]["label"]
    assert cards["claude_code"]["quota"]["status"] == "unknown" and "확인 불가" in cards["claude_code"]["quota"]["label"]
    assert cards["ollama"]["namecraft_usage"]["source_kind"] == "local_observed"
    assert "계정 전체 사용량 아님" in cards["ollama"]["namecraft_usage"]["scope"]
    assert cards["claude_code"]["namecraft_usage"]["today"]["tokens_in"] is None  # 보고값 없음 ≠ 0
    assert cards["ollama"]["namecraft_usage"]["today"]["tokens_in"] == 10
    assert b["warnings"][0]["code"] == "no_cross_provider_sum"


def test_manual_quota_alerts_and_staleness(lexicon_client):
    c = lexicon_client
    assert c.post("/api/v1/ai/usage/quotas", json={"provider_id": "ollama", "window_type": "weekly", "used_pct": 10}).status_code == 422
    r = c.post("/api/v1/ai/usage/quotas", json={"provider_id": "claude_code", "window_type": "rolling_5h", "used_pct": 92,
                                                "reset_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()}).json()
    assert r["data"]["alerts"] and "90%" in r["data"]["alerts"][0] and r["warnings"][0]["code"] == "manual_entry"
    q = c.get("/api/v1/ai/usage/quotas").json()["data"]["claude_code"][0]
    assert q["source_kind"] == "manual" and q["remaining_pct"] == 8.0 and 100 <= q["reset_in_minutes"] <= 120
    c.post("/api/v1/ai/usage/quotas", json={"provider_id": "claude_code", "window_type": "weekly", "used_pct": 30,
                                            "reset_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()})
    weekly = next(x for x in c.get("/api/v1/ai/usage/quotas").json()["data"]["claude_code"] if x["window_type"] == "weekly")
    assert weekly["source_kind"] == "stale"  # 초기화 시각이 지남
    alerts = c.get("/api/v1/ai/alerts").json()["data"]
    assert alerts[0]["level"] == "critical" and alerts[0]["source_kind"] == "manual"
    c.patch("/api/v1/ai/alert-rules", json={"provider_id": "antigravity", "enabled": False})
    r2 = c.post("/api/v1/ai/usage/quotas", json={"provider_id": "antigravity", "window_type": "model_group", "used_pct": 99})
    assert r2.json()["data"]["alerts"] == []
    assert c.post("/api/v1/ai/usage/quotas", json={"provider_id": "claude_code", "window_type": "weekly"}).status_code == 400


def test_demo_data_is_excluded_from_usage_apis(lexicon_client, lexicon_session):
    from namecraft.services.usage import load_demo

    assert load_demo(lexicon_session)["sessions"] > 0
    lexicon_session.commit()
    c = lexicon_client
    assert c.post("/api/v1/ai/usage/demo").status_code == 404
    summary = c.get("/api/v1/ai/usage/summary?include_demo=true").json()["data"]
    assert all(row["namecraft_usage"]["30d"]["requests"] == 0 for row in summary["providers"])
    assert c.get("/api/v1/ai/sessions?include_demo=true").json()["data"] == []
    assert c.get("/api/v1/ai/usage/quotas?include_demo=true").json()["data"]["claude_code"] == []
    assert c.get("/api/v1/ai/usage/heatmap?include_demo=true").json()["data"]["model_distribution"] == []


def test_timeseries_heatmap_export_sync(lexicon_client, lexicon_session):
    lexicon_session.add(AIInvocation(provider_id="ollama", execution_mode="native_local", model_id="m",
                                     task="explain_name", status="success", duration_ms=500))
    lexicon_session.commit()
    ts = lexicon_client.get("/api/v1/ai/usage/timeseries?metric=latency_ms&days=7").json()["data"]
    assert ts["unit"] == "ms" and len(ts["days"]) == 7 and set(ts["series"]) == {"ollama", "claude_code", "antigravity"}
    assert ts["series"]["ollama"][-1]["value"] == 500 and ts["series"]["claude_code"][-1]["value"] is None
    req = lexicon_client.get("/api/v1/ai/usage/timeseries?metric=requests&days=7").json()["data"]
    assert req["series"]["claude_code"][-1]["value"] == 0
    assert lexicon_client.get("/api/v1/ai/usage/timeseries?days=5").status_code == 400
    hm = lexicon_client.get("/api/v1/ai/usage/heatmap").json()["data"]
    assert sum(map(sum, hm["weekday_hour"])) == 1 and hm["model_distribution"][0]["model_id"] == "m"
    csv_ = lexicon_client.get("/api/v1/ai/usage/export?format=csv").content.decode("utf-8")
    assert csv_.startswith("﻿observed_at,provider_id") and "prompt" not in csv_
    js = lexicon_client.get("/api/v1/ai/usage/export?format=json").json()
    assert js["invocations"][0]["task"] == "explain_name" and "프롬프트" in js["note"]
    lexicon_session.add(AIInvocation(provider_id="claude_code", execution_mode="manual_handoff",
                                     model_id="historic", task="explain_name", status="success"))
    lexicon_session.commit()
    local = lexicon_client.get("/api/v1/ai/usage/heatmap?provider=ollama").json()["data"]
    assert sum(map(sum, local["weekday_hour"])) == 1
    assert [m["provider_id"] for m in local["model_distribution"]] == ["ollama"]
    exported = lexicon_client.get("/api/v1/ai/usage/export?format=json&provider=ollama").json()
    assert [r["provider_id"] for r in exported["invocations"]] == ["ollama"]
    assert exported["quota_snapshots"] == []
    sync = lexicon_client.post("/api/v1/ai/usage/sync").json()["data"]
    assert sync["claude_code"]["result"] == "not_supported" and sync["ollama"]["result"] == "nothing_to_sync"


def test_local_spike_alert_only_without_official_pct(lexicon_client, lexicon_session):
    now = datetime.now(UTC)
    lexicon_session.add_all([AIInvocation(provider_id="ollama", execution_mode="native_local", task="t", status="success",
                                          observed_at=now - timedelta(minutes=i)) for i in range(6)])
    lexicon_session.commit()
    lexicon_client.get("/api/v1/ai/usage/summary")
    lexicon_client.get("/api/v1/ai/usage/summary")  # 하루 한 번만
    spikes = [a for a in lexicon_client.get("/api/v1/ai/alerts").json()["data"] if a["kind"] == "local_spike"]
    assert len(spikes) == 1 and spikes[0]["source_kind"] == "local_observed" and spikes[0]["level"] == "info"


def test_usage_settings_retention(lexicon_client, lexicon_session):
    lexicon_session.add(AIInvocation(provider_id="ollama", execution_mode="x", task="t", status="success",
                                     observed_at=datetime.now(UTC) - timedelta(days=400)))
    lexicon_session.commit()
    s = lexicon_client.get("/api/v1/ai/usage/settings").json()["data"]
    assert s["retention_days"] == 180 and s["local_log_collection"]["status"] == "not_supported"
    lexicon_client.patch("/api/v1/ai/usage/settings", json={"retention_days": 365})
    assert lexicon_client.post("/api/v1/ai/usage/purge").json()["data"]["deleted_invocations"] == 1
