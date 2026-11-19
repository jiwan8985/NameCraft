"""실제로 쓰이는 이름 사전 + 이름에 즐겨 쓰는 좋은 뜻 한자 (datasets/rules/given-names.yaml, name-hanja.yaml).

규칙 기반 생성은 이 사전 안에서만 이름을 고르고, 한자 제안도 큐레이션된 좋은 뜻 한자 안에서만 한다.
(이전 방식: 음절 기계 조합 → '라로', '로라(勞羅)', '하람(下濫)' 같은 어색한 이름이 나왔음)
"""

from __future__ import annotations

from functools import lru_cache

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from namecraft.config import REPO_ROOT
from namecraft.db.models import HanjaCharacter, HanjaReading
from namecraft.domain.text import codepoint


@lru_cache(maxsize=1)
def given_names() -> dict[str, dict]:
    d = yaml.safe_load((REPO_ROOT / "datasets" / "rules" / "given-names.yaml").read_text(encoding="utf-8"))["names"]
    return {n: {**v, "rank": i} for i, (n, v) in enumerate(d.items())}


@lru_cache(maxsize=1)
def name_hanja() -> dict[str, list[tuple[str, str]]]:
    d = yaml.safe_load((REPO_ROOT / "datasets" / "rules" / "name-hanja.yaml").read_text(encoding="utf-8"))["hanja"]
    return {syl: [(h, m) for h, m in lst] for syl, lst in d.items()}


def meaning_ko(char: str, syllable: str | None = None) -> str | None:
    """'상서로울 서' 같은 훈음. 큐레이션 목록에 있을 때만."""
    for syl, lst in name_hanja().items():
        if syllable and syl != syllable:
            continue
        for h, m in lst:
            if h == char:
                return f"{m} {syl}"
    return None


def curated_chars(session: Session, syllable: str, exclude: set[str] = frozenset()) -> list[str]:
    """큐레이션 한자 중 DB 에 그 독음(두음법칙 변형 포함)이 실제로 있는 글자만, 목록 순서대로."""
    chars = [h for h, _ in name_hanja().get(syllable, []) if h not in exclude]
    if not chars:
        return []
    have = set(session.scalars(select(HanjaCharacter.char)
                               .join(HanjaReading, HanjaReading.codepoint == HanjaCharacter.codepoint)
                               .where(HanjaReading.reading == syllable,
                                      HanjaCharacter.codepoint.in_([codepoint(c) for c in chars]))))
    return [c for c in chars if c in have]


def is_hangul_only(name: str) -> bool:
    """순우리말이거나, 좋은 뜻 한자가 없는 음절(엘·루 등)이 있으면 한글 이름으로만 제안."""
    info = given_names().get(name)
    if info and info["style"] == "native":
        return True
    return any(c not in name_hanja() for c in name)


def is_trend(name: str) -> bool:
    return bool(given_names().get(name, {}).get("trend"))
