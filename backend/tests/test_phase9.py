"""Phase 9 게이트: 예정→확정 변경 및 이력 보존 + 시나리오·가족·토너먼트·결선 (기획서 §11, §12)."""

from __future__ import annotations

from datetime import date, time

import pytest

from namecraft.domain.calendar import interpretation as interp
from namecraft.services import scenarios as sc


# ---------------------------------------------------------------- 시나리오 엔진

def test_scenarios_window_and_time_range_no_averaging():
    r = sc.evaluate(calendar="solar", base_date=date(2027, 1, 15), is_leap_month=False, time_=None,
                    time_range=(time(9), time(12)), tz="Asia/Seoul", longitude=None, true_solar_time="off",
                    zi_convention="jojasi_next_day", day_window=1)
    assert r["dates"] == ["2027-01-14", "2027-01-15", "2027-01-16"]
    assert r["scenario_count"] == 6  # 날짜마다 巳·午 두 구간
    assert set(r["varying_pillars"]) == {"day", "hour"}
    assert all(v["min"] <= v["max"] for v in r["element_ranges"].values())
    assert "average" not in str(r).lower()
    assert any("평균하지 않습니다" in n for n in r["notes"])


def test_scenarios_extra_dates_and_limits():
    kw = dict(calendar="solar", base_date=date(2027, 1, 15), is_leap_month=False, time_range=None, tz="Asia/Seoul",
              longitude=None, true_solar_time="off", zi_convention="jojasi_next_day", extra_dates=[date(2027, 2, 4)])
    before = sc.evaluate(time_=time(10), **kw)  # 2/4 10:00 은 입춘(10:46) 전 → 연·월주 같음
    assert before["dates"] == ["2027-01-15", "2027-02-04"] and before["varying_pillars"] == ["day"]
    after = sc.evaluate(time_=time(11), **kw)  # 입춘 후 → 연·월주가 바뀜
    assert {"year", "month"} <= set(after["varying_pillars"])
    with pytest.raises(sc.ScenarioInputError):
        sc.scenario_dates(date(2027, 1, 15), 8, [])


def test_interpretation_complement_and_sensitivity():
    counts = {"木": 0, "火": 3, "土": 2, "金": 2, "水": 1}
    assert interp.weak_strong(counts) == (["木"], ["火"])
    assert interp.complement_score(counts, ["木", None])["score"] == 100.0
    assert interp.complement_score(counts, ["火"])["score"] == 25.0
    assert interp.complement_score(counts, [None])["score"] is None
    assert interp.sensitivity_label([50, 55]) == "low" and interp.sensitivity_label([20, 80]) == "high"
    assert "반드시" in interp.DISCLAIMER and "아닙니다" in interp.DISCLAIMER


def test_scenario_api(client, auth):
    r = client.post("/api/v1/scenarios/evaluate", headers=auth, json={
        "date": "2027-01-15", "time_range": ["09:00", "12:00"], "day_window": 1,
        "names": [{"label": "智雅", "jawon": [None, None]}, {"label": "林", "jawon": ["木"]}]})
    b = r.json()
    assert r.status_code == 200 and {w["code"] for w in b["warnings"]} >= {"no_averaging"}
    names = {n["label"]: n for n in b["data"]["names"]}
    assert names["智雅"]["sensitivity"] == "not_available" and names["林"]["min"] is not None
    assert client.post("/api/v1/scenarios/evaluate", headers=auth, json={"date": "2027-01-15", "day_window": 9}).status_code == 422


# ---------------------------------------------------------------- 출생정보 버전 (게이트)

def _project(c, **prefs):
    return c.post("/api/v1/projects", json={"surname_hangul": "심", "surname_hanja": "沈", "sex": "f",
                                            "preferences": {"name_type": "any", "count": 5, **prefs}}).json()["data"]


def test_expected_to_actual_preserves_history(lexicon_client):
    p = _project(lexicon_client)
    e = lexicon_client.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={
        "kind": "expected", "date": "2027-01-15", "time_range": ["09:00", "12:00"], "day_window": 2}).json()["data"]
    assert e["scenario"]["scenario_count"] == 10
    a = lexicon_client.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={
        "kind": "actual", "date": "2027-01-16", "time": "10:42"})
    assert a.status_code == 201 and "reevaluated" in {w["code"] for w in a.json()["warnings"]}
    assert a.json()["data"]["scenario"]["scenario_count"] == 1
    hist = lexicon_client.get(f"/api/v1/projects/{p['id']}/birth-profiles").json()["data"]
    assert [h["kind"] for h in hist] == ["expected", "actual"]
    assert hist[0]["is_current"] is False and hist[0]["superseded_at"] and hist[0]["snapshots"]
    assert hist[1]["is_current"] is True
    # 이전 예정 시나리오 스냅샷을 그대로 다시 볼 수 있음
    old = lexicon_client.get(f"/api/v1/scenario-snapshots/{hist[0]['snapshots'][0]['id']}").json()["data"]
    assert old["scenario"]["scenario_count"] == 10 and old["scenario"]["dates"][0] == "2027-01-13"
    cur = lexicon_client.get(f"/api/v1/projects/{p['id']}/scenario").json()["data"]
    assert cur["profile"]["kind"] == "actual"


def test_birth_profile_validation(lexicon_client):
    p = _project(lexicon_client)
    bad = lexicon_client.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={
        "kind": "actual", "date": "2027-01-16", "day_window": 1})
    assert bad.status_code == 400
    leap = lexicon_client.post(f"/api/v1/projects/{p['id']}/birth-profiles", json={
        "calendar": "lunar", "date": "2024-03-01", "is_leap_month": True})
    assert leap.status_code == 422
    # 실패한 입력은 기존 현재 정보를 바꾸지 않음
    assert lexicon_client.get(f"/api/v1/projects/{p['id']}/birth-profiles").json()["data"] == []
    assert lexicon_client.get(f"/api/v1/projects/{p['id']}/scenario").json()["warnings"][0]["code"] == "no_birth_profile"


def test_ranking_saju_only_when_enabled_and_profile_exists(lexicon_client):
    off = _project(lexicon_client)
    on = _project(lexicon_client, use_saju=True)
    for p in (off, on):
        lexicon_client.post(f"/api/v1/projects/{p['id']}/candidates", json={"given_hangul": "수림", "given_hanja": "秀林"})
    s_on = lexicon_client.get(f"/api/v1/projects/{on['id']}/candidates").json()["data"]["items"][0]["categories"]["saju"]
    assert s_on["score"] is None and "출생정보" in s_on["basis"]
    lexicon_client.post(f"/api/v1/projects/{on['id']}/birth-profiles", json={"date": "2027-01-15", "day_window": 1,
                                                                             "time_range": ["09:00", "12:00"]})
    s_on = lexicon_client.get(f"/api/v1/projects/{on['id']}/candidates").json()["data"]["items"][0]["categories"]["saju"]
    assert s_on["score"] is not None and "평균 아님" in s_on["basis"] and s_on["sensitivity"] in ("low", "medium", "high")
    assert s_on["score"] == s_on["range"][0]
    lexicon_client.post(f"/api/v1/projects/{off['id']}/birth-profiles", json={"date": "2027-01-15"})
    s_off = lexicon_client.get(f"/api/v1/projects/{off['id']}/candidates").json()["data"]["items"][0]["categories"]["saju"]
    assert s_off["score"] is None and "미사용" in s_off["basis"]


# ---------------------------------------------------------------- 가족

def _cands(c, pid, names):
    return [c.post(f"/api/v1/projects/{pid}/candidates", json={"given_hangul": n}).json()["data"]["id"] for n in names]


def test_family_votes_common_and_disagreement(lexicon_client):
    p = _project(lexicon_client)
    a, b, c3 = _cands(lexicon_client, p["id"], ["지아", "하은", "수아"])
    mom = lexicon_client.post(f"/api/v1/projects/{p['id']}/members", json={"alias": "엄마"}).json()["data"]["id"]
    dad = lexicon_client.post(f"/api/v1/projects/{p['id']}/members", json={"alias": "아빠"}).json()["data"]["id"]
    vote = lambda m, cid, r, rank=None: lexicon_client.post("/api/v1/family/votes", json={  # noqa: E731
        "member_id": m, "candidate_id": cid, "reaction": r, "rank": rank})
    vote(mom, a, "like", 1); vote(dad, a, "like", 2)
    vote(mom, b, "like"); vote(dad, b, "dislike")
    vote(mom, c3, "hold")
    s = lexicon_client.get(f"/api/v1/projects/{p['id']}/family").json()["data"]
    assert [r["given_hangul"] for r in s["common"]] == ["지아"]
    assert [r["given_hangul"] for r in s["disagreements"]] == ["하은"]
    jia = next(r for r in s["candidates"] if r["given_hangul"] == "지아")
    assert jia["votes"][mom]["rank"] == 1 and jia["avg_rank"] is None  # 순위는 평균 내지 않음
    # 한 구성원의 싫어요는 후보를 제외시키지 않음
    names = {i["given_hangul"] for i in lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]}
    assert "하은" in names
    assert vote("nope", a, "like").status_code == 404


# ---------------------------------------------------------------- 토너먼트

def test_tournament_flow_with_hold_and_bye(lexicon_client):
    p = _project(lexicon_client)
    ids = _cands(lexicon_client, p["id"], ["지아", "하은", "수아", "서윤"])
    t = lexicon_client.post("/api/v1/tournaments", json={"project_id": p["id"], "candidate_ids": ids}).json()["data"]
    tid = t["id"]
    vote = lambda i, ch: lexicon_client.post(f"/api/v1/tournaments/{tid}/vote", json={"match_index": i, "choice": ch})  # noqa: E731
    vote(0, "a")
    r = vote(1, "hold").json()["data"]  # 하은 vs ... → 수아·서윤 둘 다 진출
    assert len(r["rounds"]) == 2 and len(r["rounds"][1]) == 2 and r["rounds"][1][1]["choice"] == "bye"
    r = vote(0, "b").json()["data"]  # 지아 vs 수아 → 수아, 서윤 부전승
    r = vote(0, "a").json()["data"]
    assert r["status"] == "done" and r["result"]["winner_name"] == "수아" and not r["result"]["tied"]
    assert vote(0, "a").status_code == 400  # 끝난 토너먼트
    hist = lexicon_client.get(f"/api/v1/projects/{p['id']}/tournaments").json()["data"]
    assert len(hist) == 1 and len(hist[0]["rounds"]) == 3


def test_tournament_all_hold_ends_tied(lexicon_client):
    p = _project(lexicon_client)
    ids = _cands(lexicon_client, p["id"], ["지아", "하은"])
    tid = lexicon_client.post("/api/v1/tournaments", json={"project_id": p["id"], "candidate_ids": ids}).json()["data"]["id"]
    r = lexicon_client.post(f"/api/v1/tournaments/{tid}/vote", json={"match_index": 0, "choice": "hold"}).json()["data"]
    assert r["status"] == "done" and r["result"]["tied"] and r["result"]["winner"] is None
    assert len(r["result"]["finalists"]) == 2
    bad = lexicon_client.post("/api/v1/tournaments", json={"project_id": p["id"], "candidate_ids": [ids[0]]})
    assert bad.status_code == 422


# ---------------------------------------------------------------- 결선·결정

def test_finalists_board_and_decision_history(lexicon_client):
    p = _project(lexicon_client)
    ids = _cands(lexicon_client, p["id"], ["지아", "하은", "수아", "서윤"])
    assert lexicon_client.put(f"/api/v1/projects/{p['id']}/finalists", json={"candidate_ids": ids[:2]}).status_code == 422
    lexicon_client.put(f"/api/v1/projects/{p['id']}/finalists", json={"candidate_ids": ids[:3]})
    board = lexicon_client.get(f"/api/v1/projects/{p['id']}/finalists/board").json()["data"]
    assert len(board["finalists"]) == 3 and all("scenario_sensitivity" in f for f in board["finalists"])
    assert lexicon_client.post(f"/api/v1/projects/{p['id']}/decision",
                               json={"candidate_id": ids[3], "reason": "x"}).status_code == 400  # 결선 밖
    ok = lexicon_client.post(f"/api/v1/projects/{p['id']}/decision",
                             json={"candidate_id": ids[0], "reason": "부르기 쉽고 가족 모두 좋아함"}).json()
    assert ok["data"]["chosen_candidate_id"] == ids[0] and ok["warnings"][0]["code"] == "official_recheck"
    # 다른 결선 구성으로 다시 → 이전 결정 보존
    lexicon_client.put(f"/api/v1/projects/{p['id']}/finalists", json={"candidate_ids": ids[1:4]})
    ds = lexicon_client.get(f"/api/v1/projects/{p['id']}/decisions").json()["data"]
    assert len(ds) == 2 and ds[0]["chosen_candidate_id"] == ids[0] and ds[0]["has_snapshot"] and not ds[0]["is_current"]
    # 선택하지 않은 후보도 그대로 남아 있음 (복구 가능)
    items = lexicon_client.get(f"/api/v1/projects/{p['id']}/candidates").json()["data"]["items"]
    assert len(items) == 4 and next(i for i in items if i["id"] == ids[0])["status"] == "favorite"
