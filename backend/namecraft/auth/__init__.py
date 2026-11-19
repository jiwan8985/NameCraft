"""개인용 로컬 인증 (기획서 §20 '기본 개인용 계정 인증').

- 최초 실행 시 무작위 토큰을 `var/local_token`에 생성(파일 권한 0600 시도).
- API는 127.0.0.1 바인딩 + `Authorization: Bearer <token>` 확인. `/api/v1/health`만 예외.
- 웹 앱은 Next.js 서버 측 프록시가 토큰을 붙인다 — 브라우저에 토큰을 노출하지 않는다.
- 다중 사용자/가족 초대는 Phase 9 이후 확장.
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from namecraft.errors import Unauthorized


def ensure_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows 등 일부 FS에서 무시
        pass
    return token


def verify_bearer(header_value: str | None, expected: str) -> None:
    if not header_value or not header_value.lower().startswith("bearer "):
        raise Unauthorized("인증 토큰이 필요합니다.")
    supplied = header_value[7:].strip()
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise Unauthorized("인증 토큰이 올바르지 않습니다.")
