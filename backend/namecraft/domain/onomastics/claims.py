"""금지 표현 검사 (REQ-NF-005). 결과에 걸리면 해당 문장을 차단·수정해야 한다."""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from namecraft.config import REPO_ROOT


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[str, re.Pattern]]:
    doc = yaml.safe_load((REPO_ROOT / "datasets" / "rules" / "forbidden-claims.yaml").read_text(encoding="utf-8"))
    return [(p["id"], re.compile(p["regex"])) for p in doc["patterns"]]


def find_forbidden_claims(text: str) -> list[dict]:
    return [{"id": pid, "match": m.group(0)} for pid, rx in _patterns() for m in rx.finditer(text)]
