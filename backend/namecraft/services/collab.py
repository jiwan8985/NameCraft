"""출생정보 버전·시나리오 스냅샷·가족 평가·토너먼트·결선/결정 (기획서 §11, §12, REQ-SIM/FAM/FIN)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import (
    BirthProfile, FamilyMember, FinalNameDecision, NameCandidate, NameReaction, ScenarioResult, Tournament,
)
from namecraft.domain.calendar import interpretation as interp
from namecraft.errors import AppError, NotFound
from namecraft.services import projects as ps
from namecraft.services import scenarios as sc


class CollabError(AppError):
    status_code = 400
    code = "invalid_request"


# ---------------------------------------------------------------- 출생정보 버전

def profile_dict(b: BirthProfile) -> dict:
    return {"id": b.id, "kind": b.kind, "calendar": b.calendar, "date": b.date, "is_leap_month": b.is_leap_month,
            "time": b.time, "time_range": b.time_range, "tz": b.tz, "longitude": b.longitude,
            "true_solar_time": b.true_solar_time, "zi_convention": b.zi_convention, "day_window": b.day_window,
            "extra_dates": b.extra_dates, "is_current": b.is_current, "created_at": b.created_at.isoformat(),
            "superseded_at": b.superseded_at.isoformat() if b.superseded_at else None}


def current_profile(session: Session, project_id: str) -> BirthProfile | None:
    return session.scalars(select(BirthProfile).where(BirthProfile.project_id == project_id,
                                                      BirthProfile.is_current.is_(True))).first()


def add_birth_profile(session: Session, project_id: str, data: dict) -> tuple[BirthProfile, ScenarioResult]:
    ps.get_project(session, project_id)
    if data["kind"] == "actual" and not data.get("time") and not data.get("time_range"):
        pass  # 실제 출생이라도 시각을 모를 수 있음 — 시간 미정으로 계산
    if data["kind"] == "actual" and (data.get("day_window") or data.get("extra_dates")):
        raise CollabError("확정된 출생정보에는 예정일 범위·후보 날짜를 쓸 수 없습니다.")
    b = BirthProfile(project_id=project_id, **data)
    # 먼저 계산해 입력 오류를 확인한 뒤 이전 버전을 대체(이전 기록은 삭제하지 않음)
    result = _evaluate_profile(session, project_id, b)
    for old in session.scalars(select(BirthProfile).where(BirthProfile.project_id == project_id,
                                                          BirthProfile.is_current.is_(True))):
        old.is_current = False
        old.superseded_at = datetime.now(UTC)
    session.add(b)
    session.flush()
    snap = ScenarioResult(project_id=project_id, birth_profile_id=b.id, engine_version=result["engine_version"],
                          rule_version=result["rule_version"], interpretation_profile=interp.PROFILE_ID,
                          summary=result)
    session.add(snap)
    session.flush()
    return b, snap


def _jawon_for(session: Session, p, cands: list[NameCandidate]) -> list[dict]:
    from namecraft.domain.numerology.core import NumerologyOptions
    from namecraft.services.numerology import analyze_name

    out = []
    for c in cands:
        if not c.given_hanja:
            out.append({"label": c.given_hangul, "candidate_id": c.id, "jawon": []})
            continue
        r = analyze_name(session, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                         given_hangul=c.given_hangul, given_hanja=c.given_hanja, opts=NumerologyOptions())
        jw = r.get("trad", {}).get("jawon", {}).get("elements", [])
        out.append({"label": c.given_hangul + (f"({c.given_hanja})" if c.given_hanja else ""), "candidate_id": c.id,
                    "jawon": jw[len(p.surname_hangul):]})  # 이름 글자만
    return out


def _evaluate_profile(session: Session, project_id: str, b: BirthProfile) -> dict:
    p = ps.get_project(session, project_id)
    tr = tuple(time.fromisoformat(x) for x in b.time_range) if b.time_range else None
    names = None
    if p.preferences.get("use_saju"):
        cands = [c for c in ps.candidates(session, project_id) if c.status in ("active", "favorite")][:30]
        names = _jawon_for(session, p, cands)
    return sc.evaluate(calendar=b.calendar, base_date=date.fromisoformat(b.date), is_leap_month=b.is_leap_month,
                       time_=time.fromisoformat(b.time) if b.time else None, time_range=tr, tz=b.tz,
                       longitude=b.longitude, true_solar_time=b.true_solar_time, zi_convention=b.zi_convention,
                       day_window=b.day_window, extra_dates=[date.fromisoformat(d) for d in b.extra_dates],
                       names=names)


def refresh_scenarios(session: Session, project_id: str) -> ScenarioResult:
    b = current_profile(session, project_id)
    if b is None:
        raise CollabError("출생정보(예정 또는 확정)를 먼저 입력하세요.")
    result = _evaluate_profile(session, project_id, b)
    snap = ScenarioResult(project_id=project_id, birth_profile_id=b.id, engine_version=result["engine_version"],
                          rule_version=result["rule_version"], interpretation_profile=interp.PROFILE_ID,
                          summary=result)
    session.add(snap)
    session.flush()
    return snap


def latest_snapshot(session: Session, project_id: str) -> ScenarioResult | None:
    b = current_profile(session, project_id)
    if b is None:
        return None
    return session.scalars(select(ScenarioResult).where(ScenarioResult.birth_profile_id == b.id)
                           .order_by(ScenarioResult.created_at.desc())).first()


def history(session: Session, project_id: str) -> list[dict]:
    rows = []
    for b in session.scalars(select(BirthProfile).where(BirthProfile.project_id == project_id)
                             .order_by(BirthProfile.created_at)):
        snaps = session.scalars(select(ScenarioResult).where(ScenarioResult.birth_profile_id == b.id)
                                .order_by(ScenarioResult.created_at)).all()
        rows.append({**profile_dict(b), "snapshots": [
            {"id": s.id, "created_at": s.created_at.isoformat(), "scenario_count": s.summary.get("scenario_count"),
             "distinct_charts": s.summary.get("distinct_charts"), "engine_version": s.engine_version} for s in snaps]})
    return rows


# ---------------------------------------------------------------- 가족 공동 평가

def add_member(session: Session, project_id: str, alias: str, role: str) -> FamilyMember:
    ps.get_project(session, project_id)
    alias = alias.strip()
    if not alias:
        raise CollabError("별칭이 필요합니다.")
    m = FamilyMember(project_id=project_id, alias=alias, role=role)
    session.add(m)
    session.flush()
    return m


def members(session: Session, project_id: str) -> list[FamilyMember]:
    return list(session.scalars(select(FamilyMember).where(FamilyMember.project_id == project_id)
                                .order_by(FamilyMember.created_at)))


def family_vote(session: Session, *, member_id: str, candidate_id: str, reaction: str, rank: int | None,
                memo: str | None) -> NameReaction:
    m = session.get(FamilyMember, member_id)
    c = session.get(NameCandidate, candidate_id)
    if m is None or c is None or m.project_id != c.project_id:
        raise NotFound("구성원 또는 후보를 찾을 수 없습니다.")
    if reaction not in ("like", "dislike", "hold"):
        raise CollabError("reaction 은 like | dislike | hold 입니다.")
    # 가족 구성원의 반응은 후보 상태(제외)를 바꾸지 않는다 — 의견 차이를 보여주기 위함
    r = NameReaction(candidate_id=c.id, member=f"member:{m.id}", reaction=reaction, rank=rank, memo=memo or None)
    session.add(r)
    session.flush()
    return r


def family_summary(session: Session, project_id: str) -> dict[str, Any]:
    ms = members(session, project_id)
    cands = {c.id: c for c in ps.candidates(session, project_id, include_excluded=True)}
    latest: dict[tuple[str, str], NameReaction] = {}
    for r in session.scalars(select(NameReaction).join(NameCandidate, NameCandidate.id == NameReaction.candidate_id)
                             .where(NameCandidate.project_id == project_id, NameReaction.member.like("member:%"))
                             .order_by(NameReaction.created_at)):
        latest[(r.candidate_id, r.member)] = r
    rows = []
    for cid, c in cands.items():
        votes = {m.id: latest.get((cid, f"member:{m.id}")) for m in ms}
        if not any(votes.values()):
            continue
        reactions = [v.reaction for v in votes.values() if v]
        rows.append({
            "candidate_id": cid, "given_hangul": c.given_hangul, "given_hanja": c.given_hanja or None,
            "votes": {mid: ({"reaction": v.reaction, "rank": v.rank, "memo": v.memo} if v else None)
                      for mid, v in votes.items()},
            "all_like": len(reactions) == len(ms) and all(x == "like" for x in reactions),
            "disagreement": "like" in reactions and "dislike" in reactions,
            "like_count": reactions.count("like"), "voted": len(reactions),
            "avg_rank": None,  # 순위는 평균 내지 않고 구성원별로 보여준다
        })
    rows.sort(key=lambda r: (-r["like_count"], r["given_hangul"]))
    return {"members": [{"id": m.id, "alias": m.alias, "role": m.role} for m in ms], "candidates": rows,
            "common": [r for r in rows if r["all_like"]], "disagreements": [r for r in rows if r["disagreement"]]}


# ---------------------------------------------------------------- 토너먼트

def _pairs(entrants: list[str]) -> list[dict]:
    matches = []
    for i in range(0, len(entrants), 2):
        if i + 1 < len(entrants):
            matches.append({"a": entrants[i], "b": entrants[i + 1], "choice": None})
        else:
            matches.append({"a": entrants[i], "b": None, "choice": "bye"})  # 부전승
    return matches


def create_tournament(session: Session, project_id: str, candidate_ids: list[str], member: str) -> Tournament:
    ps.get_project(session, project_id)
    if not 2 <= len(candidate_ids) <= 16 or len(set(candidate_ids)) != len(candidate_ids):
        raise CollabError("토너먼트 후보는 서로 다른 2~16개입니다.")
    valid = {c.id for c in ps.candidates(session, project_id, include_excluded=True)}
    if not set(candidate_ids) <= valid:
        raise CollabError("이 프로젝트의 후보만 넣을 수 있습니다.")
    t = Tournament(project_id=project_id, member=member, rounds=[_pairs(candidate_ids)])
    session.add(t)
    session.flush()
    return t


def tournament_vote(session: Session, tournament_id: str, match_index: int, choice: str) -> Tournament:
    t = session.get(Tournament, tournament_id)
    if t is None:
        raise NotFound("토너먼트를 찾을 수 없습니다.")
    if t.status != "active":
        raise CollabError("이미 끝난 토너먼트입니다.")
    if choice not in ("a", "b", "hold"):
        raise CollabError("choice 는 a | b | hold 입니다.")
    rounds = [list(map(dict, r)) for r in t.rounds]
    cur = rounds[-1]
    if not 0 <= match_index < len(cur) or cur[match_index]["choice"] == "bye":
        raise CollabError("잘못된 대결 번호입니다.")
    cur[match_index]["choice"] = choice
    if all(m["choice"] is not None for m in cur):
        advancing: list[str] = []
        for m in cur:
            if m["choice"] == "bye":
                advancing.append(m["a"])
            elif m["choice"] == "a":
                advancing.append(m["a"])
            elif m["choice"] == "b":
                advancing.append(m["b"])
            else:  # hold: 둘 다 다음 라운드로 (결정 보류)
                advancing += [m["a"], m["b"]]
        prev = sum(1 if m["b"] is None else 2 for m in cur)
        if len(advancing) == 1:
            t.status, t.result = "done", {"winner": advancing[0], "finalists": advancing, "tied": False}
        elif len(advancing) >= prev:  # 이번 라운드에서 아무도 줄지 않음 → 보류 상태로 종료
            t.status, t.result = "done", {"winner": None, "finalists": advancing, "tied": True}
        else:
            rounds.append(_pairs(advancing))
        if t.status == "done":
            t.finished_at = datetime.now(UTC)
    t.rounds = rounds
    session.flush()
    return t


def tournament_dict(session: Session, t: Tournament) -> dict:
    names = {c.id: c.given_hangul + (f"({c.given_hanja})" if c.given_hanja else "")
             for c in ps.candidates(session, t.project_id, include_excluded=True)}
    return {"id": t.id, "project_id": t.project_id, "member": t.member, "status": t.status,
            "rounds": [[{**m, "a_name": names.get(m["a"]), "b_name": names.get(m["b"]) if m["b"] else None}
                        for m in r] for r in t.rounds],
            "result": {**t.result, "winner_name": names.get(t.result.get("winner")) if t.result else None,
                       "finalist_names": [names.get(x) for x in t.result.get("finalists", [])] if t.result else []},
            "created_at": t.created_at.isoformat(), "finished_at": t.finished_at.isoformat() if t.finished_at else None}


# ---------------------------------------------------------------- 결선 보드·결정

def set_finalists(session: Session, project_id: str, candidate_ids: list[str]) -> FinalNameDecision:
    if not 3 <= len(candidate_ids) <= 5 or len(set(candidate_ids)) != len(candidate_ids):
        raise CollabError("결선 후보는 서로 다른 3~5개입니다.")
    valid = {c.id for c in ps.candidates(session, project_id, include_excluded=True)}
    if not set(candidate_ids) <= valid:
        raise CollabError("이 프로젝트의 후보만 결선에 올릴 수 있습니다.")
    for old in session.scalars(select(FinalNameDecision).where(FinalNameDecision.project_id == project_id,
                                                               FinalNameDecision.is_current.is_(True))):
        old.is_current = False
    b = current_profile(session, project_id)
    d = FinalNameDecision(project_id=project_id, finalists=candidate_ids, birth_profile_id=b.id if b else None)
    session.add(d)
    session.flush()
    return d


def current_board(session: Session, project_id: str) -> FinalNameDecision | None:
    return session.scalars(select(FinalNameDecision).where(FinalNameDecision.project_id == project_id,
                                                           FinalNameDecision.is_current.is_(True))).first()


def decide(session: Session, project_id: str, candidate_id: str, reason: str, board_snapshot: dict) -> FinalNameDecision:
    d = current_board(session, project_id)
    if d is None:
        raise CollabError("결선 후보를 먼저 정하세요.")
    if candidate_id not in d.finalists:
        raise CollabError("결선 후보 중에서 선택하세요.")
    if not reason.strip():
        raise CollabError("선택 이유를 기록하세요.")
    d.chosen_candidate_id, d.reason, d.snapshot = candidate_id, reason.strip(), board_snapshot
    c = session.get(NameCandidate, candidate_id)
    if c is not None:
        c.status = "favorite"  # 다른 후보는 그대로 남아 복구 가능
    session.flush()
    return d


def decisions(session: Session, project_id: str) -> list[dict]:
    return [{"id": d.id, "finalists": d.finalists, "chosen_candidate_id": d.chosen_candidate_id, "reason": d.reason,
             "is_current": d.is_current, "birth_profile_id": d.birth_profile_id, "created_at": d.created_at.isoformat(),
             "has_snapshot": bool(d.snapshot)}
            for d in session.scalars(select(FinalNameDecision).where(FinalNameDecision.project_id == project_id)
                                     .order_by(FinalNameDecision.created_at))]
