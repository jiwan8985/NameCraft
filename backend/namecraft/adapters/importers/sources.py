"""datasets/source-manifests/*.yaml → reference_sources 동기화."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from namecraft.config import REPO_ROOT
from namecraft.db.models import ReferenceSource

MANIFEST_DIR = REPO_ROOT / "datasets" / "source-manifests"

# 사용자 입력 임시 레코드용 내부 출처 (manifest 파일 없음)
USER_INPUT_SOURCE = "SRC-USER-INPUT"


def _dt(v):
    if v is None or isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    return datetime.fromisoformat(str(v))


def sync_manifests(session: Session, manifest_dir: Path = MANIFEST_DIR) -> int:
    n = 0
    for f in sorted(manifest_dir.glob("*.yaml")):
        m = yaml.safe_load(f.read_text(encoding="utf-8"))
        src = session.get(ReferenceSource, m["id"]) or ReferenceSource(id=m["id"])
        src.name, src.url, src.authority = m["name"], m.get("url") or None, m["authority"]
        src.license, src.license_verified_at = m.get("license"), _dt(m.get("license_verified_at"))
        src.status, src.notes = m["status"], m.get("notes") or None
        session.add(src)
        n += 1
    if session.get(ReferenceSource, USER_INPUT_SOURCE) is None:
        session.add(ReferenceSource(id=USER_INPUT_SOURCE, name="사용자 직접 입력", authority="user_input",
                                    status="approved", notes="검증 전용 임시 레코드 — 확정 판정 보류"))
        n += 1
    session.flush()
    return n
