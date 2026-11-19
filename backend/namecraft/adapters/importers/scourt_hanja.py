"""대법원 인명용 한자표 가져오기 (SRC-SCOURT-HANJA).

공식 첨부 파일의 원본 형식(HWP/PDF/XLSX 등)은 공개 시점마다 다를 수 있으므로, 먼저 사람이 검토하여
아래 **정규화 CSV**로 변환한 뒤 가져온다(자동 스크래핑 금지, REQ-HJ-004).

정규화 CSV 헤더 (UTF-8):
    hanja,reading,effective_date,legal_basis
    沈,심,2024-06-11,가족관계의 등록 등에 관한 규칙 제37조 별표1

- `hanja`는 원본의 코드포인트를 그대로 보존한다(호환 한자 접지 금지).
- `is_sample=True`로 가져온 레코드는 API에서 절대 `verified`로 표시되지 않는다.
- Unihan 힌트와 공식 결과가 다르면 hanja_characters.record_status 를 conflict 로 표시한다(공식값 우선).
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from namecraft.adapters.importers.common import sha256_file, upsert_release
from namecraft.db.models import HanjaCharacter, HanjaReading, OfficialNameCharacterRule
from namecraft.domain.text import codepoint, is_hanja, normalize_name_text

SOURCE_ID = "SRC-SCOURT-HANJA"
REQUIRED = ["hanja", "reading", "effective_date", "legal_basis"]


class ImportFormatError(ValueError):
    pass


def import_official_csv(session: Session, path: Path, *, is_sample: bool) -> dict:
    checksum = sha256_file(path)
    release_id = f"scourt-hanja-{'sample-' if is_sample else ''}{checksum[:8]}"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows or any(col not in rows[0] for col in REQUIRED):
        raise ImportFormatError(f"CSV 헤더는 {REQUIRED} 를 포함해야 합니다.")

    upsert_release(session, release_id, "대법원 인명용 한자표(정규화 CSV)" + (" — SAMPLE" if is_sample else ""),
                   {path.name: checksum}, is_sample=is_sample)
    session.execute(delete(OfficialNameCharacterRule).where(OfficialNameCharacterRule.is_sample == is_sample))

    stats = {"rules": 0, "conflicts": 0, "unknown_chars": 0, "release_id": release_id}
    for i, r in enumerate(rows, start=2):
        hanja = normalize_name_text(r["hanja"])
        reading = normalize_name_text(r["reading"])
        if len(hanja) != 1 or not is_hanja(hanja) or not reading:
            raise ImportFormatError(f"{path.name}:{i} 형식 오류")
        cp = codepoint(hanja)
        session.add(OfficialNameCharacterRule(
            codepoint=cp, reading=reading, allowed=True, legal_basis=r["legal_basis"] or None,
            effective_date=r["effective_date"] or None, source_id=SOURCE_ID, data_release_id=release_id,
            is_sample=is_sample,
        ))
        stats["rules"] += 1
        ch = session.get(HanjaCharacter, cp)
        if ch is None:
            stats["unknown_chars"] += 1
            continue
        hint = set(session.scalars(select(HanjaReading.reading).where(
            HanjaReading.codepoint == cp, HanjaReading.is_name_reading.is_(True))))
        if not is_sample and hint and reading not in hint:
            ch.record_status = "conflict"
            stats["conflicts"] += 1
    session.flush()
    return stats
