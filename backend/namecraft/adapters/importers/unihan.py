"""Unicode Unihan → 한자 기초 데이터 (SRC-UNIHAN).

- 법적 근거가 아니므로 모든 레코드는 `unverified` (REQ-HJ-002/003).
- 대상: 한국 독음(kHangul) 또는 kKoreanName 이 있는 글자.
- 현대 필획: kTotalStrokes. 값이 2개면 UAX #38 규정상 첫째=zh-Hans, 둘째=zh-Hant 선호값이므로
  정자(번체) 기반인 한국 한자에는 **둘째 값**을 쓴다 (rule STROKE.MODERN.UNIHAN.v1).
- kHangul 플래그: 0/1/2 = KS X 1001/1002/… 수록, E = 교육용 기초한자 독음, N = 인명용 추가 한자 독음.
  인명용 한자 = 교육용 기초한자 + 인명용 추가한자표(가족관계등록규칙 제37조) 이므로 E 또는 N 이면
  `is_name_reading=True` 로 표시한다. 단, Unihan의 반영 시점(kKoreanName 2015/2018)이 현행 고시와
  다를 수 있으므로 법적 판정에는 쓰지 않는다.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from namecraft.adapters.importers.common import sha256_file, upsert_release
from namecraft.db.models import HanjaCharacter, HanjaReading, HanjaStrokeCount, HanjaVariant
from namecraft.domain.text import char_from_codepoint

SOURCE_ID = "SRC-UNIHAN"
STROKE_RULE = "STROKE.MODERN.UNIHAN.v1"
WANTED = {
    "kHangul", "kDefinition", "kTotalStrokes", "kRSUnicode", "kKoreanName", "kKoreanEducationHanja",
    "kCompatibilityVariant", "kTraditionalVariant", "kSimplifiedVariant", "kSemanticVariant", "kZVariant",
}
VARIANT_TYPES = {
    "kCompatibilityVariant": "compatibility", "kTraditionalVariant": "traditional",
    "kSimplifiedVariant": "simplified", "kSemanticVariant": "semantic", "kZVariant": "z",
}
_VERSION_RE = re.compile(r"^# Unicode Version (\S+)")
_HANGUL_RE = re.compile(r"^(?P<reading>[가-힣]+):(?P<flags>[0-9A-Z]*)$")


@dataclass
class UnihanEntry:
    codepoint: str
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def readings(self) -> list[tuple[str, str]]:
        out = []
        for tok in self.fields.get("kHangul", "").split():
            m = _HANGUL_RE.match(tok)
            if m:
                out.append((m["reading"], m["flags"]))
        return out

    @property
    def modern_strokes(self) -> int | None:
        vals = self.fields.get("kTotalStrokes", "").split()
        return int(vals[-1]) if vals else None


def parse_unihan_zip(data: bytes) -> tuple[str | None, dict[str, UnihanEntry]]:
    entries: dict[str, UnihanEntry] = {}
    version = None
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith(".txt"):
                continue
            for line in io.TextIOWrapper(zf.open(name), encoding="utf-8"):
                if line.startswith("#"):
                    if version is None and (m := _VERSION_RE.match(line)):
                        version = m.group(1)
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 3 or parts[1] not in WANTED:
                    continue
                cp, key, value = parts
                entries.setdefault(cp, UnihanEntry(cp)).fields[key] = value
    korean = {cp: e for cp, e in entries.items() if "kHangul" in e.fields or "kKoreanName" in e.fields}
    return version, korean


def _variant_targets(value: str) -> list[str]:
    # "U+4E18" 또는 "U+4E94<kMatthews" 형태
    return [tok.split("<")[0] for tok in value.split() if tok.startswith("U+")]


def import_unihan(session: Session, zip_path: Path, *, is_sample: bool = False) -> dict:
    data = zip_path.read_bytes()
    checksum = sha256_file(zip_path)
    version, entries = parse_unihan_zip(data)
    release_id = f"unihan-{version or 'unknown'}-{checksum[:8]}"
    upsert_release(session, release_id, f"Unicode Unihan {version} (kHangul/kKoreanName subset)",
                   {zip_path.name: checksum}, is_sample=is_sample)

    # 재실행 대비: 이 출처의 파생 레코드 교체 (다른 출처 레코드는 보존)
    for model in (HanjaReading, HanjaStrokeCount, HanjaVariant):
        session.execute(delete(model).where(model.source_id == SOURCE_ID))

    existing = {c.codepoint: c for c in session.query(HanjaCharacter).all()}
    stats = defaultdict(int)
    for cp, e in entries.items():
        f = e.fields
        compat_targets = _variant_targets(f.get("kCompatibilityVariant", ""))
        ch = existing.get(cp) or HanjaCharacter(codepoint=cp, source_id=SOURCE_ID)
        ch.char = char_from_codepoint(cp)
        ch.is_compatibility = bool(compat_targets)
        ch.canonical_codepoint = compat_targets[0] if compat_targets else cp
        ch.radical_stroke = f.get("kRSUnicode")
        ch.definition_en = f.get("kDefinition")
        ch.unihan_korean_name = f.get("kKoreanName")
        ch.unihan_korean_education = f.get("kKoreanEducationHanja")
        ch.data_release_id = ch.data_release_id or release_id
        if cp not in existing:
            session.add(ch)
            existing[cp] = ch
        stats["characters"] += 1

        for reading, flags in e.readings:
            session.add(HanjaReading(
                codepoint=cp, reading=reading, flags=flags or None,
                is_name_reading=("N" in flags or "E" in flags),
                source_id=SOURCE_ID, status="unverified", data_release_id=release_id,
            ))
            stats["readings"] += 1
        if (n := e.modern_strokes) is not None:
            session.add(HanjaStrokeCount(codepoint=cp, system="modern", strokes=n, rule_id=STROKE_RULE,
                                         source_id=SOURCE_ID, status="unverified"))
            stats["strokes"] += 1
        for key, vtype in VARIANT_TYPES.items():
            for target in _variant_targets(f.get(key, "")):
                session.add(HanjaVariant(codepoint=cp, variant_codepoint=target, variant_type=vtype,
                                         source_id=SOURCE_ID))
                stats["variants"] += 1
    session.flush()
    return {"release_id": release_id, "unicode_version": version, "checksum": checksum, **stats}
