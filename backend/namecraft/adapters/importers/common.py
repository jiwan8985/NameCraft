from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from namecraft.db.models import DataReleaseVersion


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_release(session: Session, release_id: str, description: str, checksums: dict, *, is_sample: bool) -> str:
    rel = session.get(DataReleaseVersion, release_id)
    if rel is None:
        session.add(DataReleaseVersion(id=release_id, description=description, checksums=checksums, is_sample=is_sample))
    else:
        rel.description, rel.checksums, rel.is_sample = description, checksums, is_sample
    session.flush()
    return release_id
