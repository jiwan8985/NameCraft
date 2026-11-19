"""성씨 시드 가져오기 + Unihan 독음 자동 대조."""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from namecraft.adapters.importers.common import sha256_file, upsert_release
from namecraft.config import REPO_ROOT
from namecraft.db.models import HanjaReading, Surname, SurnameVariant
from namecraft.domain.text import codepoint, normalize_name_text

SOURCE_ID = "SRC-DEV-SURNAME-SEED"
SEED_PATH = REPO_ROOT / "datasets" / "seed" / "surnames.yaml"


def _known_readings(session: Session, cp: str) -> set[str]:
    return set(session.scalars(select(HanjaReading.reading).where(HanjaReading.codepoint == cp)))


def import_surname_seed(session: Session, path: Path = SEED_PATH) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    checksum = sha256_file(path)
    release_id = f"surname-seed-{checksum[:8]}"
    upsert_release(session, release_id, "개발자 큐레이션 성씨 시드", {path.name: checksum}, is_sample=False)

    old_ids = list(session.scalars(select(Surname.id).where(Surname.source_id == SOURCE_ID)))
    session.execute(delete(SurnameVariant).where(SurnameVariant.surname_id.in_(old_ids)))
    session.execute(delete(Surname).where(Surname.source_id == SOURCE_ID))

    stats = {"surnames": 0, "conflicts": 0, "release_id": release_id}
    for item in doc["surnames"]:
        hangul = normalize_name_text(item["hangul"])
        hanja = normalize_name_text(item["hanja"])
        alts = [normalize_name_text(a) for a in item.get("alt", [])]
        cps = [codepoint(c) for c in hanja]
        notes: list[str] = []
        conflict = False
        if len(hangul) != len(hanja):
            notes.append("한글·한자 글자 수 불일치")
            conflict = True
        else:
            spellings = [hangul, *alts]
            for i, cp in enumerate(cps):
                known = _known_readings(session, cp)
                if known and not any(s[i] in known for s in spellings if len(s) == len(hanja)):
                    notes.append(f"{hanja[i]}({cp}) 독음 '{hangul[i]}'이(가) Unihan kHangul {sorted(known)}에 없음")
                    conflict = True
                elif not known:
                    notes.append(f"{hanja[i]}({cp}) Unihan 독음 정보 없음")
        s = Surname(hangul=hangul, hanja=hanja, hanja_codepoints=cps, is_compound=bool(item.get("compound")),
                    record_status="conflict" if conflict else "unverified", source_id=SOURCE_ID,
                    note="; ".join(notes) or None)
        session.add(s)
        session.flush()
        for a in alts:
            session.add(SurnameVariant(surname_id=s.id, hangul=a))
        stats["surnames"] += 1
        stats["conflicts"] += int(conflict)
    session.flush()
    return stats
