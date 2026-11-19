"""개인정보 최소 로그 (기획서 §20, REQ-NF-006).

로그 레코드의 `extra`로 전달된 민감 키 값과, 메시지 내 날짜·시각 패턴을 마스킹한다.
원칙적으로 이름·출생정보는 로그 메시지에 넣지 않는다 — 이 필터는 실수 방지용 안전망이다.
"""

from __future__ import annotations

import logging
import re

SENSITIVE_KEYS = frozenset(
    {
        "name", "given_name", "surname", "full_name", "hangul", "hanja",
        "birth_date", "birth_time", "birth_datetime", "birthplace", "family_names",
        "prompt", "token", "authorization", "cookie",
    }
)
_DATE_RE = re.compile(r"\b(19|20)\d{2}[-./](0?[1-9]|1[0-2])[-./](0?[1-9]|[12]\d|3[01])\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
REDACTED = "[REDACTED]"


def redact_text(text: str) -> str:
    text = _BEARER_RE.sub("Bearer " + REDACTED, text)
    text = _DATE_RE.sub(REDACTED, text)
    return _TIME_RE.sub(REDACTED, text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key.lower() in SENSITIVE_KEYS:
                setattr(record, key, REDACTED)
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args) \
                if isinstance(record.args, tuple) else record.args
        return True


def install() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(RedactingFilter())
    for handler in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
