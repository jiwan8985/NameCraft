"""AI Usage Center (기획서 §30, §33.2, REQ-USG-001~009).

원칙
- Provider 간 수치를 합산하지 않는다. 단위가 다른 지표를 한 축에 섞지 않는다.
- NameCraft 내부 사용량(ai_invocations, local_observed)과 계정 전체 한도(ai_quota_snapshots, manual/official)를 구분한다.
- 공식 수치를 확인할 수 없으면 '확인 불가'. 숫자를 꾸며내지 않는다. Ollama 는 '로컬 / 한도 없음 / 해당 없음'.
- DEMO 데이터는 is_demo 로 분리하며 실제 집계·알림에 섞지 않는다(요청 시에만 별도 표시).
- 사용량 DB 에는 프롬프트 원문·토큰·쿠키·출생정보를 저장하지 않는다.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from namecraft.config import REPO_ROOT
from namecraft.db.models import AIAlertEvent, AIAlertRule, AIInvocation, AIQuotaSnapshot, AppSetting
from namecraft.errors import AppError

PROVIDERS = ("ollama", "claude_code", "antigravity")
LABELS = {"ollama": "Ollama", "claude_code": "Claude Code", "antigravity": "Google Antigravity"}
WINDOW_TYPES = ("rolling_5h", "weekly", "daily", "model_group", "other")
METRICS = {"requests": "count", "tokens_in": "tokens", "tokens_out": "tokens", "latency_ms": "ms"}
DEFAULT_THRESHOLDS = [50, 75, 90, 100]
STALE_AFTER = timedelta(hours=24)


class UsageError(AppError):
    status_code = 400
    code = "usage_invalid"


def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


def _inv_q(include_demo: bool):
    q = select(AIInvocation)
    return q if include_demo else q.where(AIInvocation.is_demo.is_(False))


# ---------------------------------------------------------------- 내부 사용량

def _window_stats(rows: list[AIInvocation]) -> dict:
    if not rows:
        return {"requests": 0, "success_rate": None, "avg_latency_ms": None, "tokens_in": None, "tokens_out": None}
    ok = sum(1 for r in rows if r.status == "success")
    lat = [r.duration_ms for r in rows if r.duration_ms is not None]
    tin = [r.tokens_in for r in rows if r.tokens_in is not None]
    tout = [r.tokens_out for r in rows if r.tokens_out is not None]
    return {"requests": len(rows), "success_rate": round(ok / len(rows), 3),
            "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
            "tokens_in": sum(tin) if tin else None,  # 보고된 값이 하나도 없으면 0 이 아니라 None
            "tokens_out": sum(tout) if tout else None}


def latest_quotas(session: Session, provider_id: str, include_demo: bool = False) -> list[dict]:
    q = select(AIQuotaSnapshot).where(AIQuotaSnapshot.provider_id == provider_id)
    if not include_demo:
        q = q.where(AIQuotaSnapshot.is_demo.is_(False))
    latest: dict[tuple, AIQuotaSnapshot] = {}
    for s in session.scalars(q.order_by(AIQuotaSnapshot.observed_at)):
        latest[(s.account_alias, s.model_group, s.window_type)] = s
    now = datetime.now(UTC)
    out = []
    for s in latest.values():
        reset = _aware(s.reset_at)
        observed = _aware(s.observed_at)
        stale = (reset is not None and reset <= now) or (observed is not None and now - observed > STALE_AFTER)
        out.append({"id": s.id, "account_alias": s.account_alias, "model_group": s.model_group,
                    "window_type": s.window_type, "used_pct": s.used_pct,
                    "remaining_pct": None if s.used_pct is None else round(100 - s.used_pct, 1),
                    "remaining_text": s.remaining_text, "reset_at": reset.isoformat() if reset else None,
                    "reset_in_minutes": int((reset - now).total_seconds() // 60) if reset and reset > now else None,
                    "observed_at": observed.isoformat() if observed else None,
                    "source_kind": "stale" if stale else s.source_kind, "original_source_kind": s.source_kind,
                    "note": s.note, "is_demo": s.is_demo})
    return out


def summary(session: Session, statuses: dict[str, dict], include_demo: bool = False, *, provider: str | None = None) -> dict:
    now = datetime.now(UTC)
    rows = list(session.scalars(_inv_q(include_demo).where(AIInvocation.observed_at >= now - timedelta(days=30))))
    cards = []
    for pid in ([provider] if provider else PROVIDERS):
        mine = [r for r in rows if r.provider_id == pid]
        by_window = {}
        for label, days in (("today", 1), ("7d", 7), ("30d", 30)):
            by_window[label] = _window_stats([r for r in mine if _aware(r.observed_at) >= now - timedelta(days=days)])
        models = Counter(r.model_id for r in mine if r.model_id)
        st = statuses.get(pid, {})
        if pid == "ollama":
            quota = {"status": "not_applicable", "label": "로컬 / 한도 없음 / 해당 없음", "windows": []}
        else:
            windows = latest_quotas(session, pid, include_demo)
            quota = {"status": "available" if windows else "unknown",
                     "label": "수동·공식 입력값" if windows else "확인 불가 — 공식 /usage 화면 값을 직접 입력할 수 있습니다",
                     "windows": windows}
        cards.append({
            "provider_id": pid, "label": LABELS[pid],
            "connection": {"state": st.get("state"), "execution_mode": st.get("execution_mode"),
                           "version": st.get("version"), "enabled": st.get("enabled"), "message": st.get("message")},
            "namecraft_usage": {"scope": "NameCraft 안에서 실행한 요청만 — 계정 전체 사용량 아님",
                                "source_kind": "local_observed", **by_window},
            "top_models": models.most_common(3),
            "quota": quota,
        })
    return {"providers": cards, "generated_at": now.isoformat(), "include_demo": include_demo,
            "rules": ["Provider 간 수치는 합산하지 않습니다.", "토큰·요청·퍼센트는 서로 다른 단위입니다.",
                      "구독 한도는 공식 화면 값을 옮겨 적은 경우에만 표시합니다."]}


def timeseries(session: Session, *, metric: str, days: int, tz: str = "Asia/Seoul",
               include_demo: bool = False) -> dict:
    if metric not in METRICS:
        raise UsageError(f"metric: {list(METRICS)}")
    if days not in (7, 30, 90):
        raise UsageError("기간은 7·30·90일입니다.")
    zone = ZoneInfo(tz)
    now = datetime.now(UTC)
    start = (now - timedelta(days=days - 1)).astimezone(zone).date()
    rows = list(session.scalars(_inv_q(include_demo).where(AIInvocation.observed_at >= now - timedelta(days=days + 1))))
    series: dict[str, dict[str, list]] = {p: defaultdict(list) for p in PROVIDERS}
    for r in rows:
        day = _aware(r.observed_at).astimezone(zone).date()
        if day < start or r.provider_id not in series:
            continue
        val = 1 if metric == "requests" else getattr(r, metric if metric != "latency_ms" else "duration_ms")
        if val is not None:
            series[r.provider_id][day.isoformat()].append(val)
    days_list = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    agg = (lambda xs: sum(xs)) if metric != "latency_ms" else (lambda xs: round(sum(xs) / len(xs)))
    out = {p: [{"date": d, "value": agg(series[p][d]) if series[p].get(d) else (0 if metric == "requests" else None)}
               for d in days_list] for p in PROVIDERS}
    return {"metric": metric, "unit": METRICS[metric], "days": days_list, "series": out, "tz": tz,
            "include_demo": include_demo, "source_kind": "local_observed",
            "note": "Provider 별 별도 계열 — 합계 없음. 값이 없는 날은 null(0 아님, 요청 수 제외)."}


def heatmap(session: Session, *, days: int = 30, tz: str = "Asia/Seoul", include_demo: bool = False,
            provider: str | None = None) -> dict:
    zone = ZoneInfo(tz)
    query = _inv_q(include_demo).where(AIInvocation.observed_at >= datetime.now(UTC) - timedelta(days=days))
    if provider:
        query = query.where(AIInvocation.provider_id == provider)
    rows = list(session.scalars(query))
    grid = [[0] * 24 for _ in range(7)]
    for r in rows:
        t = _aware(r.observed_at).astimezone(zone)
        grid[t.weekday()][t.hour] += 1
    models = Counter((r.provider_id, r.model_id or "unknown") for r in rows)
    return {"weekday_hour": grid, "weekdays": ["월", "화", "수", "목", "금", "토", "일"], "days": days, "tz": tz,
            "model_distribution": [{"provider_id": p, "model_id": m, "requests": n} for (p, m), n in models.most_common()],
            "include_demo": include_demo}


def sessions(session: Session, *, provider: str | None, status: str | None, q: str | None, limit: int,
             include_demo: bool = False) -> list[dict]:
    query = _inv_q(include_demo)
    if provider:
        query = query.where(AIInvocation.provider_id == provider)
    if status:
        query = query.where(AIInvocation.status == status)
    if q:
        like = f"%{q}%"
        query = query.where(AIInvocation.task.like(like) | AIInvocation.model_id.like(like))
    rows = session.scalars(query.order_by(AIInvocation.observed_at.desc()).limit(min(limit, 500)))
    return [{"id": r.id, "provider_id": r.provider_id, "model_id": r.model_id, "execution_mode": r.execution_mode,
             "task": r.task, "status": r.status, "duration_ms": r.duration_ms, "tokens_in": r.tokens_in,
             "tokens_out": r.tokens_out, "observed_at": _aware(r.observed_at).isoformat(), "source_type": r.source_type,
             "quota_data_status": r.quota_data_status, "is_demo": r.is_demo, "project_attached": bool(r.project_id)}
            for r in rows]


# ---------------------------------------------------------------- 한도 입력·알림

def rule_for(session: Session, provider_id: str) -> AIAlertRule:
    return session.get(AIAlertRule, provider_id) or AIAlertRule(provider_id=provider_id, thresholds=DEFAULT_THRESHOLDS,
                                                                local_spike_factor=2.0, enabled=True)


def add_quota(session: Session, data: dict) -> tuple[AIQuotaSnapshot, list[AIAlertEvent]]:
    if data["provider_id"] == "ollama":
        raise UsageError("Ollama 는 로컬 실행이라 구독 한도가 없습니다.")
    if data["provider_id"] not in PROVIDERS or data["window_type"] not in WINDOW_TYPES:
        raise UsageError("provider_id·window_type 값이 올바르지 않습니다.")
    pct = data.get("used_pct")
    if pct is not None and not 0 <= pct <= 100:
        raise UsageError("사용률은 0~100% 입니다.")
    if pct is None and not data.get("remaining_text"):
        raise UsageError("사용률 또는 잔여량(원본 단위) 중 하나는 필요합니다.")
    s = AIQuotaSnapshot(**{k: v for k, v in data.items() if v is not None}, source_kind="manual")
    session.add(s)
    session.flush()
    events = []
    rule = rule_for(session, s.provider_id)
    if rule.enabled and pct is not None:
        crossed = [t for t in sorted(rule.thresholds) if pct >= t]
        if crossed:
            t = crossed[-1]
            level = "critical" if t >= 90 else "warn" if t >= 75 else "info"
            e = AIAlertEvent(provider_id=s.provider_id, kind="quota_threshold", level=level, source_kind="manual",
                             snapshot_id=s.id,
                             message=f"{LABELS[s.provider_id]} {s.window_type} 사용률 {pct:g}% — {t}% 기준 도달 (수동 입력값)")
            session.add(e)
            events.append(e)
    session.flush()
    return s, events


def check_local_spike(session: Session) -> list[AIAlertEvent]:
    """공식 사용률이 없는 Provider 에는 한도 경고 대신 '로컬 이벤트 증가 알림'만 (§33.2)."""
    now = datetime.now(UTC)
    events = []
    for pid in PROVIDERS:
        rule = rule_for(session, pid)
        if not rule.enabled:
            continue
        rows = list(session.scalars(select(AIInvocation).where(
            AIInvocation.provider_id == pid, AIInvocation.is_demo.is_(False),
            AIInvocation.observed_at >= now - timedelta(days=8))))
        today = sum(1 for r in rows if _aware(r.observed_at) >= now - timedelta(days=1))
        week = [r for r in rows if _aware(r.observed_at) < now - timedelta(days=1)]
        avg = len(week) / 7
        if today >= 5 and today >= avg * rule.local_spike_factor:
            dup = session.scalar(select(func.count()).select_from(AIAlertEvent).where(
                AIAlertEvent.provider_id == pid, AIAlertEvent.kind == "local_spike",
                AIAlertEvent.created_at >= now - timedelta(days=1)))
            if not dup:
                e = AIAlertEvent(provider_id=pid, kind="local_spike", level="info", source_kind="local_observed",
                                 message=f"{LABELS[pid]} NameCraft 요청이 오늘 {today}건으로 최근 평균({avg:.1f}건/일)보다 많습니다.")
                session.add(e)
                events.append(e)
    session.flush()
    return events


def alerts(session: Session, include_demo: bool = False) -> list[dict]:
    q = select(AIAlertEvent)
    if not include_demo:
        q = q.where(AIAlertEvent.is_demo.is_(False))
    return [{"id": e.id, "provider_id": e.provider_id, "kind": e.kind, "level": e.level, "message": e.message,
             "source_kind": e.source_kind, "created_at": _aware(e.created_at).isoformat(),
             "acknowledged": e.acknowledged, "is_demo": e.is_demo}
            for e in session.scalars(q.order_by(AIAlertEvent.created_at.desc()).limit(200))]


# ---------------------------------------------------------------- DEMO · 내보내기 · 보존

def load_demo(session: Session) -> dict:
    doc = json.loads((REPO_ROOT / "datasets" / "fixtures" / "ai-usage-demo.json").read_text(encoding="utf-8"))
    clear_demo(session)
    now = datetime.now(UTC)
    shift = now - max(datetime.fromisoformat(s["started_at"]) for s in doc["ai_sessions"])  # 최근 날짜로 이동
    for s in doc["ai_sessions"]:
        session.add(AIInvocation(provider_id=s["provider_id"], execution_mode="demo", model_id=s["model_id"],
                                 task=s["task_category"], status="success" if s["status"] == "success" else "error",
                                 duration_ms=s["duration_ms"], tokens_in=s["observed_tokens_in"],
                                 tokens_out=s["observed_tokens_out"], source_type="demo", quota_data_status="demo",
                                 observed_at=datetime.fromisoformat(s["started_at"]) + shift, is_demo=True))
    for q in doc["ai_quota_windows"]:
        if q["provider_id"] == "ollama" or q.get("used_pct") is None:
            continue
        session.add(AIQuotaSnapshot(provider_id=q["provider_id"], account_alias="DEMO", model_group=q["model_group"],
                                    window_type=q["window_type"] if q["window_type"] in WINDOW_TYPES else "other",
                                    used_pct=q["used_pct"], reset_at=now + timedelta(hours=3), observed_at=now,
                                    source_kind="demo", note="DEMO DATA", is_demo=True))
    session.flush()
    return {"sessions": len(doc["ai_sessions"])}


def clear_demo(session: Session) -> None:
    for model in (AIInvocation, AIQuotaSnapshot, AIAlertEvent):
        session.execute(delete(model).where(model.is_demo.is_(True)))
    session.flush()


def export(session: Session, fmt: str, include_demo: bool = False, *, provider: str | None = None) -> tuple[str, str]:
    inv = sessions(session, provider=provider, status=None, q=None, limit=500, include_demo=include_demo)
    quotas = [q for p in ([provider] if provider else PROVIDERS) if p != "ollama"
              for q in latest_quotas(session, p, include_demo)]
    if fmt == "json":
        return json.dumps({"invocations": inv, "quota_snapshots": quotas, "exported_at": datetime.now(UTC).isoformat(),
                           "note": "NameCraft 내부 실행 기록과 수동 입력 한도만 포함 — 프롬프트·인증 정보 없음"},
                          ensure_ascii=False, indent=1), "application/json"
    if fmt != "csv":
        raise UsageError("format: csv | json")
    buf = io.StringIO()
    cols = ["observed_at", "provider_id", "model_id", "execution_mode", "task", "status", "duration_ms", "tokens_in",
            "tokens_out", "source_type", "quota_data_status", "is_demo"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in inv:
        w.writerow(r)
    return "﻿" + buf.getvalue(), "text/csv"


def get_setting(session: Session, key: str, default: dict) -> dict:
    row = session.get(AppSetting, key)
    return {**default, **(row.value if row else {})}


def set_setting(session: Session, key: str, value: dict) -> dict:
    row = session.get(AppSetting, key) or AppSetting(key=key, value={})
    row.value = {**row.value, **value}
    session.add(row)
    session.flush()
    return row.value


def purge_old(session: Session) -> dict:
    days = get_setting(session, "usage", {"retention_days": 180})["retention_days"]
    cutoff = datetime.now(UTC) - timedelta(days=days)
    n = session.execute(delete(AIInvocation).where(AIInvocation.observed_at < cutoff,
                                                   AIInvocation.is_demo.is_(False))).rowcount
    m = session.execute(delete(AIQuotaSnapshot).where(AIQuotaSnapshot.observed_at < cutoff,
                                                      AIQuotaSnapshot.is_demo.is_(False))).rowcount
    session.flush()
    return {"retention_days": days, "deleted_invocations": n, "deleted_quota_snapshots": m}
