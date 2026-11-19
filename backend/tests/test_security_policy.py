"""정책 정적 검사 (기획서 §33.1, §33.4, REQ-NF-006/008, REQ-PRV-004)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from namecraft.logging_safe import REDACTED, RedactingFilter, redact_text

pytestmark = pytest.mark.security

PAID_API_KEYS = re.compile(r"(ANTHROPIC_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|OPENAI_API_KEY|VERTEX)", re.I)
FORBIDDEN_CLI_FLAGS = ("--bare", "--dangerously-skip-permissions", "--allow-dangerously-skip-permissions")
CODE_DIRS = ("backend/namecraft", "apps/api", "apps/web/src", "bridge")


def _code_files(root: Path):
    for d in CODE_DIRS:
        base = root / d
        if base.exists():
            yield from (p for p in base.rglob("*") if p.suffix in {".py", ".ts", ".tsx", ".js"}
                        and "node_modules" not in p.parts)


def test_env_example_has_no_paid_api_keys(repo_root):
    text = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert not PAID_API_KEYS.search(text)


DENYLIST_MARKERS = ("_ENV_DENY_", "FORBIDDEN_FLAGS = (", "\"--allow-dangerously-skip-permissions\"",
                    "\"--remote-agent\", \"--remote-control\")")


def test_code_never_reads_paid_api_keys_or_forbidden_flags(repo_root):
    """유료 API 키·금지 플래그 문자열은 '차단 목록 정의' 줄에만 나타날 수 있다."""
    offenders = []
    for f in _code_files(repo_root):
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(m in line for m in DENYLIST_MARKERS):
                continue
            if PAID_API_KEYS.search(line) or any(flag in line for flag in FORBIDDEN_CLI_FLAGS):
                offenders.append(f"{f.relative_to(repo_root)}:{no}")
    assert offenders == []


def test_code_does_not_touch_auth_caches(repo_root):
    pattern = re.compile(r"""["'~/\\]\.(claude|gemini|antigravity)[/\\"']""")
    assert [str(f) for f in _code_files(repo_root) if pattern.search(f.read_text(encoding="utf-8"))] == []


def test_redact_text_masks_dates_times_and_bearer():
    out = redact_text("birth 2027-01-15 09:30 Authorization: Bearer abc.def")
    assert "2027-01-15" not in out and "09:30" not in out and "abc.def" not in out
    assert out.count(REDACTED) == 3


def test_filter_masks_sensitive_extra_fields():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "project created", None, None)
    rec.given_name = "지아"  # type: ignore[attr-defined]
    RedactingFilter().filter(rec)
    assert rec.given_name == REDACTED  # type: ignore[attr-defined]


def test_filter_keeps_logger_name():
    """회귀: 로거 이름(record.name)이 민감 키 'name' 과 겹쳐 가려지던 문제."""
    rec = logging.LogRecord("namecraft.access", logging.INFO, __file__, 1, "GET /x 200", None, None)
    RedactingFilter().filter(rec)
    assert rec.name == "namecraft.access"
