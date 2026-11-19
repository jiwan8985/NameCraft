"""보안 헤더 + 개인정보 없는 접근 로그 (기획서 §20, §31.2, REQ-NF-006).

uvicorn 기본 접근 로그는 쿼리 문자열(예: ?q=심)과 경로의 ID 를 그대로 남기므로 끄고(--no-access-log),
대신 '라우트 틀'(예: /api/v1/candidates/{candidate_id})·메서드·상태·처리 시간만 기록한다.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

access_log = logging.getLogger("namecraft.access")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class SecurityAndAccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t = time.perf_counter()
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        # 개인 데이터가 담긴 응답은 브라우저·프록시 캐시 금지
        response.headers.setdefault("Cache-Control", "no-store")
        route = request.scope.get("route")
        template = getattr(route, "path", None) or "<unmatched>"
        # 포함된 라우터의 경로는 접두어 없이 기록되므로 실제 요청 경로의 접두어를 붙인다(값은 기록하지 않음)
        if template != "<unmatched>" and not template.startswith("/api/") and request.url.path.startswith("/api/v1/"):
            template = "/api/v1" + template
        access_log.info("%s %s %s %.0fms", request.method, template, response.status_code,
                        (time.perf_counter() - t) * 1000)
        return response
