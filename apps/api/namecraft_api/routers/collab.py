"""시뮬레이션·공동 선택 API (기획서 §18: POST /scenarios/evaluate, /tournaments, /family/votes) + 결선·결정."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.db.models import NameCandidate, Tournament
from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import collab as cb
from namecraft.services import projects as ps
from namecraft.services import scenarios as sc
from namecraft.services.ranking import rank_names
from namecraft_api.deps import get_db

router = APIRouter(tags=["simulation", "family"])

SCENARIO_WARNINGS = [
    {"code": "external_verification_pending", "message": "만세력 기준값의 KASI 대조가 끝나지 않았습니다(최종 단계)."},
    {"code": "no_averaging", "message": "시나리오별 결과를 평균하지 않고 경우별로 보여줍니다."},
]


class BirthIn(BaseModel):
    kind: Literal["expected", "actual"] = "expected"
    calendar: Literal["solar", "lunar"] = "solar"
    date: dt.date
    is_leap_month: bool = False
    time: dt.time | None = None
    time_range: tuple[dt.time, dt.time] | None = None
    tz: str = Field(default="Asia/Seoul", max_length=64)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    true_solar_time: Literal["off", "longitude_only", "with_equation_of_time"] = "off"
    zi_convention: Literal["jojasi_next_day", "yajasi_same_day"] = "jojasi_next_day"
    day_window: int = Field(default=0, ge=0, le=sc.MAX_WINDOW)
    extra_dates: list[dt.date] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _one_time(self):
        if self.time is not None and self.time_range is not None:
            raise ValueError("time 과 time_range 는 함께 쓸 수 없습니다.")
        return self


class ScenarioIn(BirthIn):
    names: list[dict] | None = Field(default=None, max_length=30)  # [{label, jawon:[오행|null]}]


@router.post("/scenarios/evaluate", response_model=Envelope[dict[str, Any]])
def scenarios_evaluate(body: ScenarioIn):
    data = sc.evaluate(calendar=body.calendar, base_date=body.date, is_leap_month=body.is_leap_month, time_=body.time,
                       time_range=body.time_range, tz=body.tz, longitude=body.longitude,
                       true_solar_time=body.true_solar_time, zi_convention=body.zi_convention,
                       day_window=body.day_window, extra_dates=body.extra_dates, names=body.names)
    return envelope(data, verification_status=VerificationStatus.calculated, warnings=SCENARIO_WARNINGS,
                    rule_profile="kr-common-2026", rule_version=data["rule_version"],
                    calculation_assumptions=data["assumptions"])


def _birth_data(body: BirthIn) -> dict:
    return {"kind": body.kind, "calendar": body.calendar, "date": body.date.isoformat(),
            "is_leap_month": body.is_leap_month, "time": body.time.strftime("%H:%M") if body.time else None,
            "time_range": [t.strftime("%H:%M") for t in body.time_range] if body.time_range else None,
            "tz": body.tz, "longitude": body.longitude, "true_solar_time": body.true_solar_time,
            "zi_convention": body.zi_convention, "day_window": body.day_window,
            "extra_dates": [d.isoformat() for d in body.extra_dates]}


@router.post("/projects/{project_id}/birth-profiles", response_model=Envelope[dict[str, Any]], status_code=201)
def add_birth_profile(project_id: str, body: BirthIn, db: Session = Depends(get_db)):
    b, snap = cb.add_birth_profile(db, project_id, _birth_data(body))
    db.commit()
    warnings = list(SCENARIO_WARNINGS)
    if b.kind == "actual":
        warnings.append({"code": "reevaluated", "message": "확정된 출생정보로 다시 평가했습니다. 이전 예정 정보와 평가 기록은 보존됩니다."})
    return envelope({"profile": cb.profile_dict(b), "snapshot_id": snap.id, "scenario": snap.summary},
                    warnings=warnings, verification_status=VerificationStatus.calculated)


@router.get("/projects/{project_id}/birth-profiles", response_model=Envelope[list[dict[str, Any]]])
def birth_history(project_id: str, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    return envelope(cb.history(db, project_id))


@router.get("/projects/{project_id}/scenario", response_model=Envelope[dict[str, Any]])
def project_scenario(project_id: str, refresh: bool = False, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    snap = cb.refresh_scenarios(db, project_id) if refresh else cb.latest_snapshot(db, project_id)
    if refresh:
        db.commit()
    if snap is None:
        return envelope({"profile": None, "scenario": None},
                        warnings=[{"code": "no_birth_profile", "message": "출생 예정일 또는 실제 출생정보를 입력하세요."}])
    b = cb.current_profile(db, project_id)
    return envelope({"profile": cb.profile_dict(b), "snapshot_id": snap.id, "snapshot_created_at": snap.created_at.isoformat(),
                     "scenario": snap.summary}, warnings=SCENARIO_WARNINGS,
                    verification_status=VerificationStatus.calculated)


@router.get("/scenario-snapshots/{snapshot_id}", response_model=Envelope[dict[str, Any]])
def snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    from namecraft.db.models import ScenarioResult

    s = db.get(ScenarioResult, snapshot_id)
    if s is None:
        raise NotFound("스냅샷을 찾을 수 없습니다.")
    return envelope({"id": s.id, "birth_profile_id": s.birth_profile_id, "created_at": s.created_at.isoformat(),
                     "engine_version": s.engine_version, "scenario": s.summary})


# ---------------------------------------------------------------- 가족

class MemberIn(BaseModel):
    alias: str = Field(min_length=1, max_length=30)
    role: Literal["parent", "guardian", "family", "other"] = "parent"


@router.post("/projects/{project_id}/members", response_model=Envelope[dict[str, Any]], status_code=201)
def add_member(project_id: str, body: MemberIn, db: Session = Depends(get_db)):
    m = cb.add_member(db, project_id, body.alias, body.role)
    db.commit()
    return envelope({"id": m.id, "alias": m.alias, "role": m.role})


class VoteIn(BaseModel):
    member_id: str
    candidate_id: str
    reaction: Literal["like", "dislike", "hold"]
    rank: int | None = Field(default=None, ge=1, le=100)
    memo: str | None = Field(default=None, max_length=500)


@router.post("/family/votes", response_model=Envelope[dict[str, Any]], status_code=201)
def family_vote(body: VoteIn, db: Session = Depends(get_db)):
    r = cb.family_vote(db, member_id=body.member_id, candidate_id=body.candidate_id, reaction=body.reaction,
                       rank=body.rank, memo=body.memo)
    db.commit()
    return envelope({"id": r.id, "reaction": r.reaction, "rank": r.rank})


@router.get("/projects/{project_id}/family", response_model=Envelope[dict[str, Any]])
def family_summary(project_id: str, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    return envelope(cb.family_summary(db, project_id))


# ---------------------------------------------------------------- 토너먼트

class TournamentIn(BaseModel):
    project_id: str
    candidate_ids: list[str] = Field(min_length=2, max_length=16)
    member: str = Field(default="owner", max_length=50)


@router.post("/tournaments", response_model=Envelope[dict[str, Any]], status_code=201)
def create_tournament(body: TournamentIn, db: Session = Depends(get_db)):
    t = cb.create_tournament(db, body.project_id, body.candidate_ids, body.member)
    db.commit()
    return envelope(cb.tournament_dict(db, t))


class TournamentVoteIn(BaseModel):
    match_index: int = Field(ge=0)
    choice: Literal["a", "b", "hold"]


@router.post("/tournaments/{tournament_id}/vote", response_model=Envelope[dict[str, Any]])
def tournament_vote(tournament_id: str, body: TournamentVoteIn, db: Session = Depends(get_db)):
    t = cb.tournament_vote(db, tournament_id, body.match_index, body.choice)
    db.commit()
    return envelope(cb.tournament_dict(db, t))


@router.get("/tournaments/{tournament_id}", response_model=Envelope[dict[str, Any]])
def get_tournament(tournament_id: str, db: Session = Depends(get_db)):
    t = db.get(Tournament, tournament_id)
    if t is None:
        raise NotFound("토너먼트를 찾을 수 없습니다.")
    return envelope(cb.tournament_dict(db, t))


@router.get("/projects/{project_id}/tournaments", response_model=Envelope[list[dict[str, Any]]])
def list_tournaments(project_id: str, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    rows = db.scalars(select(Tournament).where(Tournament.project_id == project_id).order_by(Tournament.created_at))
    return envelope([cb.tournament_dict(db, t) for t in rows])


# ---------------------------------------------------------------- 결선·결정

class FinalistsIn(BaseModel):
    candidate_ids: list[str] = Field(min_length=3, max_length=5)


@router.put("/projects/{project_id}/finalists", response_model=Envelope[dict[str, Any]])
def put_finalists(project_id: str, body: FinalistsIn, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    d = cb.set_finalists(db, project_id, body.candidate_ids)
    db.commit()
    return envelope({"id": d.id, "finalists": d.finalists})


@router.get("/projects/{project_id}/finalists/board", response_model=Envelope[dict[str, Any]])
def finalist_board(project_id: str, db: Session = Depends(get_db)):
    return envelope(build_board(db, project_id), verification_status=VerificationStatus.calculated,
                    warnings=[{"code": "same_standard", "message": "결선 후보를 같은 기준(가중치·학파 프로필·출생정보)으로 비교합니다."}])


def build_board(db: Session, project_id: str) -> dict:
    from namecraft_api.routers.projects import _cand, _scenarios

    p = ps.get_project(db, project_id)
    d = cb.current_board(db, project_id)
    if d is None:
        raise AppError("결선 후보를 먼저 정하세요(3~5개).")
    cands = [db.get(NameCandidate, cid) for cid in d.finalists]
    ranked = rank_names(db, surname_hangul=p.surname_hangul, surname_hanja=p.surname_hanja,
                        names=[_cand(c) for c in cands if c], weights=p.preferences.get("weights"),
                        profile=ps.profile_for(db, p.id), use_saju=bool(p.preferences.get("use_saju")),
                        saju_scenarios=_scenarios(db, p.id))
    fam = {r["candidate_id"]: r for r in cb.family_summary(db, project_id)["candidates"]}
    b = cb.current_profile(db, project_id)
    rows = []
    for it in ranked["items"]:
        saju = it["categories"]["saju"]
        rows.append({**it, "family": fam.get(it["id"]),
                     "scenario_sensitivity": saju.get("sensitivity", "not_available")})
    return {"decision_id": d.id, "finalists": rows, "chosen_candidate_id": d.chosen_candidate_id, "reason": d.reason,
            "birth_profile": cb.profile_dict(b) if b else None, "weights_normalized": ranked["weights_normalized"],
            "ranking_version": ranked["ranking_version"]}


class DecisionIn(BaseModel):
    candidate_id: str
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/projects/{project_id}/decision", response_model=Envelope[dict[str, Any]])
def decide(project_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    board = build_board(db, project_id)
    d = cb.decide(db, project_id, body.candidate_id, body.reason, board)
    db.commit()
    return envelope({"id": d.id, "chosen_candidate_id": d.chosen_candidate_id, "reason": d.reason,
                     "decided_at": d.created_at.isoformat()},
                    warnings=[{"code": "official_recheck",
                               "message": "출생신고 전에 대법원 인명용 한자 조회로 최종 확인하세요(출생신고 준비 모드는 다음 단계)."}])


@router.get("/projects/{project_id}/decisions", response_model=Envelope[list[dict[str, Any]]])
def list_decisions(project_id: str, db: Session = Depends(get_db)):
    ps.get_project(db, project_id)
    return envelope(cb.decisions(db, project_id))

