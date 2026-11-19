"""AI Provider 라우트 — Phase 1 mock (기획서 §32 Phase 1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from namecraft.ai_gateway import default_mock_providers
from namecraft.ai_gateway.protocols import ProviderId
from namecraft.errors import NotFound
from namecraft.provenance import Envelope, VerificationStatus, envelope

router = APIRouter(prefix="/ai", tags=["ai"])

_MOCK_WARNING = {"code": "mock_data", "message": "Phase 1 mock 응답입니다. 실제 연결 상태가 아닙니다."}


async def _describe(p) -> dict[str, Any]:
    status = await p.connection_status()
    status["capabilities"] = await p.capabilities()
    return status


@router.get("/providers", response_model=Envelope[list[dict[str, Any]]])
async def list_providers():
    data = [await _describe(p) for p in default_mock_providers()]
    return envelope(data, verification_status=VerificationStatus.mock, warnings=[_MOCK_WARNING])


@router.post("/providers/{provider}/test", response_model=Envelope[dict[str, Any]])
async def test_provider(provider: str):
    if provider not in ProviderId.__members__:
        raise NotFound(f"알 수 없는 Provider: {provider}", details={"allowed": list(ProviderId.__members__)})
    p = next(p for p in default_mock_providers() if p.id == provider)
    data = await _describe(p)
    data["test_result"] = "skipped_mock"
    return envelope(data, verification_status=VerificationStatus.mock, warnings=[_MOCK_WARNING])
