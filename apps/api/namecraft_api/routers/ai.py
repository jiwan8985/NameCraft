"""AI Provider 라우트 (기획서 §18, §29) — Phase 7 실제 탐지·설정·생성·수동 전달."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from namecraft.ai_gateway.protocols import ProviderId
from namecraft.ai_gateway.providers import FORBIDDEN_FLAGS, build_providers
from namecraft.db.models import AIProviderSetting
from namecraft.errors import AppError, NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope
from namecraft.services import ai_generation as aig
from namecraft.services.generation import GenerateRequest
from namecraft_api.deps import get_db

router = APIRouter(prefix="/ai", tags=["ai"])

SUBSCRIPTION_NOTE = {"code": "subscription_only",
                     "message": "Claude Code·Antigravity는 보유한 구독 계정의 공식 CLI 비대화형 모드만 사용합니다. 유료 API 키는 사용하지 않습니다."}


def _providers(request: Request, db: Session):
    return build_providers(aig.load_settings(db, request.app.state.settings.ollama_url))


async def _describe(p) -> dict[str, Any]:
    st = p.status()
    st["capabilities"] = await p.capabilities()
    return st


@router.get("/providers", response_model=Envelope[list[dict[str, Any]]])
async def list_providers(request: Request, db: Session = Depends(get_db)):
    ps = _providers(request, db)
    data = [await _describe(ps[k]) for k in ("ollama", "claude_code", "antigravity")]
    return envelope(data, verification_status=VerificationStatus.calculated, warnings=[SUBSCRIPTION_NOTE])


@router.post("/providers/{provider}/test", response_model=Envelope[dict[str, Any]])
async def test_provider(provider: str, request: Request, live: bool = False, db: Session = Depends(get_db)):
    """live=false: 읽기 전용 상태 확인(생성·한도 소모 없음). live=true: 개인정보 없는 짧은 실제 생성 1회."""
    if provider not in ProviderId.__members__:
        raise NotFound(f"알 수 없는 Provider: {provider}", details={"allowed": list(ProviderId.__members__)})
    p = _providers(request, db)[provider]
    data = await _describe(p)
    if not live:
        data["test_result"] = "status_only"
        return envelope(data, verification_status=VerificationStatus.calculated)
    return envelope({**data, **_live_test(db, provider, p, data)}, verification_status=VerificationStatus.calculated,
                    warnings=[{"code": "live_test", "message": "개인정보 없는 시험 요청 1회를 보냈습니다(구독형은 사용 한도가 조금 소모됩니다)."}])


def _live_test(db: Session, provider: str, p, status: dict) -> dict:
    import time as _t

    from namecraft.ai_gateway.providers import ProviderCallError

    if not status.get("enabled"):
        return {"test_result": "disabled", "test_message": "먼저 '사용하기'를 눌러 켜세요."}
    model = status.get("selected_model") if provider == "ollama" else p.s.model_id
    if provider == "ollama" and not model:
        return {"test_result": "no_model", "test_message": status.get("message")}
    payload = {"sex": "n", "syllables": 2, "count": 3}  # 개인정보 없음
    t = _t.monotonic()
    try:
        res = p.generate_text(aig.build_prompt(payload), system=aig.SYSTEM_PROMPT, json_schema=aig.CANDIDATES_SCHEMA,
                              seed=1, model_id=model)
    except ProviderCallError as e:
        aig._record_invocation(db, provider, "connection_test", model, None, e.kind, None, None, None)
        db.commit()
        return {"test_result": e.kind, "test_message": str(e)}
    ms = int((_t.monotonic() - t) * 1000)
    try:
        doc = aig.parse_ai_json(res.text)
        v = aig.validate_candidates(db, doc, GenerateRequest(surname_hangul="김", name_type="any"))
        result, names = "ok", [a["given_hangul"] for a in v["accepted"]]
    except Exception:
        result, names = "invalid_output", []
    aig._record_invocation(db, provider, "connection_test", res.model_id, None,
                           "success" if result == "ok" else "invalid_output", ms, res.tokens_in, res.tokens_out)
    db.commit()
    return {"test_result": result, "test_ms": ms, "test_model": res.model_id, "test_names": names,
            "test_message": f"응답 {ms / 1000:.1f}초 · 검증 통과 이름: {', '.join(names) or '없음'}" if result == "ok"
            else "응답은 왔지만 요구 형식(JSON)이 아니었습니다. 다른 모델을 골라 보세요."}


class ProviderPrefIn(BaseModel):
    provider_id: Literal["ollama", "claude_code", "antigravity"]
    enabled: bool | None = None
    command: list[str] | None = Field(default=None, max_length=8)
    model_id: str | None = Field(default=None, max_length=100)
    timeout_s: int | None = Field(default=None, ge=10, le=600)
    fallback_rank: int | None = Field(default=None, ge=0, le=99)
    allow_auto_fallback: bool | None = None


@router.patch("/preferences", response_model=Envelope[dict[str, Any]])
def patch_preferences(body: ProviderPrefIn, db: Session = Depends(get_db)):
    if body.command is not None:
        if not body.command or any(not isinstance(a, str) or not a.strip() for a in body.command):
            raise AppError("command 는 비어 있지 않은 문자열 목록이어야 합니다.")
        if any(f in body.command for f in FORBIDDEN_FLAGS):
            raise AppError("허용되지 않는 CLI 옵션이 포함되어 있습니다.", details={"forbidden": FORBIDDEN_FLAGS})
    row = db.get(AIProviderSetting, body.provider_id) or AIProviderSetting(
        provider_id=body.provider_id, enabled=body.provider_id == "ollama")
    for k in ("enabled", "command", "model_id", "timeout_s", "fallback_rank", "allow_auto_fallback"):
        v = getattr(body, k)
        if v is not None:
            setattr(row, k, v)
    db.add(row)
    db.commit()
    return envelope({k: getattr(row, k) for k in ("provider_id", "enabled", "command", "model_id", "timeout_s",
                                                  "fallback_rank", "allow_auto_fallback")},
                    warnings=[SUBSCRIPTION_NOTE] if body.provider_id != "ollama" else [])


class AIGenerateIn(BaseModel):
    provider: Literal["auto", "ollama", "claude_code", "antigravity", "none"] = "auto"
    surname_hangul: str = Field(min_length=1, max_length=4)
    sex: Literal["m", "f", "n"] = "n"
    syllables: int = Field(default=2, ge=1, le=3)
    style_tags: dict[Literal["modern", "traditional", "soft", "bright"], float] = Field(default_factory=dict)
    liked_examples: list[str] = Field(default_factory=list, max_length=30)
    include_syllables: list[str] = Field(default_factory=list, max_length=20)
    exclude_syllables: list[str] = Field(default_factory=list, max_length=50)
    count: int = Field(default=20, ge=1, le=60)
    send_fields: list[str] | None = None
    consent: bool = False
    dry_run: bool = False
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


def _req(body) -> GenerateRequest:
    return GenerateRequest(surname_hangul=body.surname_hangul, sex=body.sex, syllables=body.syllables,
                           name_type="any", style_tags=body.style_tags, liked_examples=body.liked_examples,
                           include_syllables=body.include_syllables, exclude_syllables=body.exclude_syllables,
                           count=body.count)


@router.post("/generate", response_model=Envelope[dict[str, Any]])
def ai_generate(body: AIGenerateIn, request: Request, db: Session = Depends(get_db)):
    req = _req(body)
    try:
        payload = aig.build_payload(req, body.send_fields or aig.DEFAULT_SEND)
    except ValueError as e:
        raise AppError(str(e)) from None
    if body.dry_run:
        return envelope({"preview": aig.preview(body.provider, payload)})
    try:
        res = aig.run_ai_generation(db, req, provider=body.provider, send_fields=body.send_fields,
                                    consent=body.consent, seed=body.seed,
                                    ollama_url=request.app.state.settings.ollama_url)
    except aig.AIConsentRequired as e:
        raise AppError("외부 AI 로 보내기 전에 전송 내용 확인과 동의가 필요합니다.",
                       details={"consent_required": True, "preview": e.preview}) from None
    db.commit()
    return _result_envelope(res)


def _result_envelope(res: aig.AIRunResult):
    warnings = []
    if res.fallback_reason:
        warnings.append({"code": "ai_fallback", "message": "AI 경로를 사용할 수 없어 규칙 기반 엔진으로 생성했습니다."})
    if res.provider_used != "rule_based":
        warnings.append({"code": "ai_generated",
                         "message": "AI 가 제안한 후보를 서버에서 다시 검증했습니다. AI 설명은 주관적 의견입니다."})
    return envelope({"provider_used": res.provider_used, "execution_mode": res.mode, "candidates": res.candidates,
                     "record_id": res.record_id, "fallback_reason": res.fallback_reason, "attempts": res.attempts,
                     "validation": res.validation},
                    verification_status=VerificationStatus.subjective if res.provider_used != "rule_based"
                    else VerificationStatus.calculated, warnings=warnings)


class HandoffIn(AIGenerateIn):
    provider: Literal["claude_code", "antigravity"] = "claude_code"


@router.post("/handoff/prompt", response_model=Envelope[dict[str, Any]])
def handoff_prompt(body: HandoffIn):
    try:
        payload = aig.build_payload(_req(body), body.send_fields or aig.DEFAULT_SEND)
    except ValueError as e:
        raise AppError(str(e)) from None
    return envelope({"preview": aig.preview(body.provider, payload), **aig.handoff_prompt(payload)},
                    warnings=[{"code": "manual_handoff",
                               "message": "자동 실행 대신 직접 붙여넣는 방식입니다. 붙여넣는 내용은 위 미리보기와 같습니다."}])


class HandoffImportIn(BaseModel):
    provider: Literal["claude_code", "antigravity"]
    surname_hangul: str = Field(min_length=1, max_length=4)
    syllables: int = Field(default=2, ge=1, le=3)
    pasted: str = Field(min_length=2, max_length=50_000)


@router.post("/handoff/import", response_model=Envelope[dict[str, Any]])
def handoff_import(body: HandoffImportIn, db: Session = Depends(get_db)):
    try:
        doc = aig.parse_ai_json(body.pasted)
    except Exception:
        raise AppError("붙여넣은 내용이 요구 형식(JSON)과 맞지 않습니다.", details={"schema": aig.CANDIDATES_SCHEMA}) from None
    v = aig.validate_candidates(db, doc, GenerateRequest(surname_hangul=body.surname_hangul, syllables=body.syllables,
                                                         name_type="any"))
    from namecraft.db.models import AIGenerationRecord

    rec = AIGenerationRecord(task="generate_candidates", provider_id=body.provider, execution_mode="manual_handoff",
                             prompt_version=aig.PROMPT_VERSION, status="ok" if not v["rejected"] else "partial",
                             validation={"accepted": len(v["accepted"]), "rejected": v["rejected"][:50]})
    db.add(rec)
    db.commit()
    return envelope({"provider_used": body.provider, "execution_mode": "manual_handoff", "record_id": rec.id, **v},
                    verification_status=VerificationStatus.subjective)


# ---------------------------------------------------------------- Phase 11: AI Usage Center (§18, §30)

import datetime as _dt  # noqa: E402

from fastapi import Query  # noqa: E402
from fastapi.responses import Response  # noqa: E402

from namecraft.services import usage as us  # noqa: E402

USAGE_WARNINGS = [{"code": "no_cross_provider_sum", "message": "Provider 간 수치는 합산하지 않습니다. NameCraft 내부 사용량은 계정 전체 사용량이 아닙니다."}]


def _statuses(request: Request, db: Session) -> dict:
    ps_ = _providers(request, db)
    return {k: ps_[k].status() for k in ("ollama", "claude_code", "antigravity")}


@router.get("/usage/summary", response_model=Envelope[dict[str, Any]])
def usage_summary(request: Request, include_demo: bool = False, db: Session = Depends(get_db)):
    us.check_local_spike(db)
    db.commit()
    return envelope(us.summary(db, _statuses(request, db), include_demo), warnings=USAGE_WARNINGS,
                    verification_status=VerificationStatus.calculated)


@router.get("/usage/timeseries", response_model=Envelope[dict[str, Any]])
def usage_timeseries(metric: str = "requests", days: int = 7, include_demo: bool = False,
                     tz: str = Query("Asia/Seoul", max_length=64), db: Session = Depends(get_db)):
    return envelope(us.timeseries(db, metric=metric, days=days, tz=tz, include_demo=include_demo),
                    warnings=USAGE_WARNINGS)


@router.get("/usage/heatmap", response_model=Envelope[dict[str, Any]])
def usage_heatmap(days: int = Query(30, ge=1, le=90), include_demo: bool = False, db: Session = Depends(get_db)):
    return envelope(us.heatmap(db, days=days, include_demo=include_demo))


@router.get("/usage/quotas", response_model=Envelope[dict[str, Any]])
def usage_quotas(include_demo: bool = False, db: Session = Depends(get_db)):
    return envelope({p: us.latest_quotas(db, p, include_demo) for p in ("claude_code", "antigravity")} |
                    {"ollama": {"status": "not_applicable", "label": "로컬 / 한도 없음 / 해당 없음"}})


class QuotaIn(BaseModel):
    provider_id: Literal["claude_code", "antigravity"]
    window_type: Literal["rolling_5h", "weekly", "daily", "model_group", "other"]
    model_group: str = Field(default="all", max_length=100)
    account_alias: str = Field(default="default", max_length=50)
    used_pct: float | None = Field(default=None, ge=0, le=100)
    remaining_text: str | None = Field(default=None, max_length=100)
    reset_at: _dt.datetime | None = None
    note: str | None = Field(default=None, max_length=200)


@router.post("/usage/quotas", response_model=Envelope[dict[str, Any]], status_code=201)
def add_quota(body: QuotaIn, db: Session = Depends(get_db)):
    s, events = us.add_quota(db, body.model_dump())
    db.commit()
    return envelope({"id": s.id, "alerts": [e.message for e in events]},
                    warnings=[{"code": "manual_entry", "message": "사용자 입력값으로 저장했습니다(입력 시각 기준)."}])


@router.get("/sessions", response_model=Envelope[list[dict[str, Any]]])
def ai_sessions(provider: str | None = None, status: str | None = None, q: str | None = Query(None, max_length=50),
                limit: int = Query(100, ge=1, le=500), include_demo: bool = False, db: Session = Depends(get_db)):
    return envelope(us.sessions(db, provider=provider, status=status, q=q, limit=limit, include_demo=include_demo))


@router.post("/usage/sync", response_model=Envelope[dict[str, Any]])
def usage_sync():
    """명시적 동기화 — 공식 기계 판독 인터페이스가 확인된 Provider 가 없어 수집하지 않는다(§30.2, §30.6)."""
    return envelope({"ollama": {"result": "nothing_to_sync", "message": "NameCraft 실행 기록은 호출 시 자동 저장됩니다."},
                     "claude_code": {"result": "not_supported", "message": "공식 /usage 는 대화형 화면 — 값을 직접 입력하세요."},
                     "antigravity": {"result": "not_supported", "message": "공식 /usage(/quota) 는 대화형 화면 — 값을 직접 입력하세요."}},
                    verification_status=VerificationStatus.calculated)


@router.get("/usage/export")
def usage_export(format: Literal["csv", "json"] = "csv", include_demo: bool = False, db: Session = Depends(get_db)):
    body, media = us.export(db, format, include_demo)
    return Response(body.encode("utf-8"), media_type=f"{media}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ai-usage.{format}"'})


@router.get("/alerts", response_model=Envelope[list[dict[str, Any]]])
def ai_alerts(include_demo: bool = False, db: Session = Depends(get_db)):
    return envelope(us.alerts(db, include_demo))


class AlertRuleIn(BaseModel):
    provider_id: Literal["ollama", "claude_code", "antigravity"]
    thresholds: list[int] | None = Field(default=None, max_length=6)
    local_spike_factor: float | None = Field(default=None, ge=1.1, le=20)
    enabled: bool | None = None


@router.patch("/alert-rules", response_model=Envelope[dict[str, Any]])
def patch_alert_rule(body: AlertRuleIn, db: Session = Depends(get_db)):
    from namecraft.db.models import AIAlertRule

    if body.thresholds is not None and any(not 1 <= t <= 100 for t in body.thresholds):
        raise AppError("임계치는 1~100% 입니다.")
    row = db.get(AIAlertRule, body.provider_id) or AIAlertRule(provider_id=body.provider_id,
                                                               thresholds=us.DEFAULT_THRESHOLDS, local_spike_factor=2.0)
    for k in ("thresholds", "local_spike_factor", "enabled"):
        if getattr(body, k) is not None:
            setattr(row, k, sorted(getattr(body, k)) if k == "thresholds" else getattr(body, k))
    db.add(row)
    db.commit()
    return envelope({"provider_id": row.provider_id, "thresholds": row.thresholds,
                     "local_spike_factor": row.local_spike_factor, "enabled": row.enabled})


@router.get("/alert-rules", response_model=Envelope[list[dict[str, Any]]])
def list_alert_rules(db: Session = Depends(get_db)):
    rows = [us.rule_for(db, p) for p in us.PROVIDERS]
    return envelope([{"provider_id": r.provider_id, "thresholds": r.thresholds,
                      "local_spike_factor": r.local_spike_factor, "enabled": r.enabled} for r in rows])


class UsageSettingsIn(BaseModel):
    retention_days: int | None = Field(default=None, ge=7, le=3650)
    hide_sensitive: bool | None = None


@router.get("/usage/settings", response_model=Envelope[dict[str, Any]])
def get_usage_settings(db: Session = Depends(get_db)):
    return envelope({**us.get_setting(db, "usage", {"retention_days": 180, "hide_sensitive": False}),
                     "local_log_collection": {"status": "not_supported",
                                              "message": "다른 도구의 로컬 로그·인증 폴더는 읽지 않습니다(§31.2)."}})


@router.patch("/usage/settings", response_model=Envelope[dict[str, Any]])
def patch_usage_settings(body: UsageSettingsIn, db: Session = Depends(get_db)):
    v = us.set_setting(db, "usage", body.model_dump(exclude_none=True))
    db.commit()
    return envelope(v)


@router.post("/usage/purge", response_model=Envelope[dict[str, Any]])
def usage_purge(db: Session = Depends(get_db)):
    r = us.purge_old(db)
    db.commit()
    return envelope(r)


@router.post("/usage/demo", response_model=Envelope[dict[str, Any]])
def usage_demo_load(db: Session = Depends(get_db)):
    r = us.load_demo(db)
    db.commit()
    return envelope(r, warnings=[{"code": "demo_data", "message": "DEMO DATA — 실제 사용량이 아닙니다. 'DEMO 포함'을 켰을 때만 보입니다."}])


@router.delete("/usage/demo", response_model=Envelope[dict[str, Any]])
def usage_demo_clear(db: Session = Depends(get_db)):
    us.clear_demo(db)
    db.commit()
    return envelope({"cleared": True})
