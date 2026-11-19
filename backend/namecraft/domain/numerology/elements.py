"""오행 관계 (calc): 상생·상극·비화 판별. 관계의 길흉 판단은 trad 층에서 한다."""

from __future__ import annotations

ELEMENTS = "木火土金水"
_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def relation(a: str, b: str) -> str:
    """a → b 관계: same(비화) | generates(a가 b를 생) | generated_by | controls(a가 b를 극) | controlled_by."""
    if a == b:
        return "same"
    if _GENERATES[a] == b:
        return "generates"
    if _GENERATES[b] == a:
        return "generated_by"
    if _CONTROLS[a] == b:
        return "controls"
    return "controlled_by"


RELATION_KO = {"same": "비화", "generates": "상생(→)", "generated_by": "상생(←)",
               "controls": "상극(→)", "controlled_by": "상극(←)"}


def chain(elements: list[str]) -> list[dict]:
    return [{"from": a, "to": b, "relation": relation(a, b), "label": RELATION_KO[relation(a, b)]}
            for a, b in zip(elements, elements[1:])]


def digit_element(n: int) -> str:
    """NUM.ELEMENT.v1 — 끝자리 1·2 木, 3·4 火, 5·6 土, 7·8 金, 9·0 水."""
    return "木木火火土土金金水水"[(n % 10 - 1) % 10]
