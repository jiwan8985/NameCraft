"""규칙 기반 이름 후보 생성 (기획서 §8.1 경로 1·2, §8.3, §8.4, REQ-GEN-001~004).

경로
  rule_based — 이름 음절 사전 조합 + 하드 필터 + 발음 규칙  (AI 없이 항상 동작)
  data_based — 한글 이름 예시 목록 + 사용자가 좋아한 이름의 유사음 패턴 (공개 통계 미적재 → 제한적)
  ai_based   — Phase 7

필터
  하드(제거): 포함/제외 음절·초성·한자, 돌림자, 음절 수, 제외 이름, 성과 같은 음절 반복, 한자 이름인데 인명용 독음 한자 없음
  격리(quarantine): 부정 연상 '정확' 일치(비속어·비하) — 삭제하지 않고 이유와 함께 별도 반환
  선호(점수): 성별 경향, 스타일 태그, 좋아한 이름과의 스타일 유사도, 발음 편의
다양성: 선택된 후보와 결합 유사도 ≥ 임계값이면 건너뜀, 같은 첫·끝 음절 최대 개수 제한.
결정론: 같은 입력 → 같은 결과 (무작위 없음, 동점은 이름 사전순).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy.orm import Session

from namecraft.config import REPO_ROOT
from namecraft.domain.hangul import decompose
from namecraft.domain.onomastics import analysis as la
from namecraft.domain.text import is_hangul_syllable, normalize_name_text
from namecraft.services.reverse_search import candidates_for_syllable, reverse_search

GENERATOR_VERSION = "rule-gen-0.1.0"
PRESCREEN_LIMIT = 4000  # 1단계(저비용 선호 점수) 통과 후보 수 상한 — 2단계에서 발음·주의 분석
_SONORANT = set("ㅇㄴㄹㅁ")
_BRIGHT = set("ㅏㅐㅑㅒㅗㅘㅙㅚㅛ")


@lru_cache(maxsize=1)
def lexicon() -> dict:
    return yaml.safe_load((REPO_ROOT / "datasets" / "rules" / "name-syllables.yaml").read_text(encoding="utf-8"))


class GenerationError(ValueError):
    pass


@dataclass
class GenerateRequest:
    surname_hangul: str
    surname_hanja: str | None = None
    sex: str = "n"  # m | f | n — 선호일 뿐
    syllables: int = 2  # 1~3
    name_type: str = "hanja"  # hanja | hangul | any
    include_syllables: list[str] = field(default_factory=list)  # 이 중 하나 이상 포함
    exclude_syllables: list[str] = field(default_factory=list)
    exclude_initials: list[str] = field(default_factory=list)  # 예: ["ㄹ"]
    exclude_hanja: list[str] = field(default_factory=list)
    fixed_syllable: dict[int, str] = field(default_factory=dict)  # 돌림자 {위치: 음절}
    fixed_hanja: dict[int, str] = field(default_factory=dict)  # 돌림자 한자 {위치: 한자}
    style_tags: dict[str, float] = field(default_factory=dict)  # {"modern": 1, "traditional": 0, "soft": 1, "bright": 0.5}
    liked_examples: list[str] = field(default_factory=list)  # 좋아한 이름(성 제외 또는 포함)
    exclude_names: list[str] = field(default_factory=list)
    count: int = 30
    diversity_threshold: float = 0.8
    max_same_first_syllable: int = 3
    max_same_last_syllable: int = 3
    use_traditional: bool = True


# ---------------------------------------------------------------- style features

def style_features(given: str) -> dict[str, float]:
    syl = [decompose(c) for c in given]
    return {
        "length": float(len(given)),
        "softness": sum(s[0] in _SONORANT for s in syl) / len(syl),
        "open_ratio": sum(not s[2] for s in syl) / len(syl),
        "brightness": sum(s[1] in _BRIGHT for s in syl) / len(syl),
        "ends_open": float(not syl[-1][2]),
    }


def style_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = ("softness", "open_ratio", "brightness", "ends_open")
    return (sum(abs(a[k] - b[k]) for k in keys) / len(keys)) + (0.5 if a["length"] != b["length"] else 0.0)


def _strip_surname(name: str, surname: str) -> str:
    return name[len(surname):] if name.startswith(surname) and len(name) > len(surname) else name


# ---------------------------------------------------------------- candidate pool

def _pool(req: GenerateRequest) -> list[tuple[str, str]]:
    lex = lexicon()
    syl = lex["syllables"]
    first = [s for s, v in syl.items() if v["position"] in ("first", "both")]
    second = [s for s, v in syl.items() if v["position"] in ("second", "both")]
    pool: list[tuple[str, str]] = []
    if req.syllables == 1:
        pool = [(s, "rule_based") for s in syl]
    elif req.syllables == 2:
        pool = [(a + b, "rule_based") for a in first for b in second if a != b]
    else:
        pool = [(a + m + b, "rule_based") for a in first for m in first + second for b in second
                if len({a, m, b}) == 3]
    pool += [(n, "data_based") for n in lex["native_names"] if len(n) == req.syllables]
    seen, out = set(), []
    for name, path in pool:
        if name not in seen:
            seen.add(name)
            out.append((name, path))
    return out


def _hard_filter(given: str, req: GenerateRequest, surname: str) -> str | None:
    if req.include_syllables and not any(s in given for s in req.include_syllables):
        return "include_syllables"
    if any(s in given for s in req.exclude_syllables):
        return "exclude_syllables"
    if any(decompose(c)[0] in req.exclude_initials for c in given):
        return "exclude_initials"
    for pos, s in req.fixed_syllable.items():
        if pos >= len(given) or given[pos] != s:
            return "fixed_syllable"
    if given in req.exclude_names or surname + given in req.exclude_names:
        return "excluded_by_user"
    if surname[-1] == given[0]:
        return "repeats_surname_syllable"
    return None


def _preference_score(given: str, req: GenerateRequest, liked: list[dict]) -> dict[str, Any]:
    lex = lexicon()["syllables"]
    comps: dict[str, float] = {}
    # 성별 경향 (선호)
    if req.sex in ("m", "f"):
        g = [lex.get(c, {}).get("gender", "n") for c in given]
        comps["sex_tendency"] = sum(1.0 if x == req.sex else 0.5 if x == "n" else 0.0 for x in g) / len(g)
    feats = style_features(given)
    for tag, w in req.style_tags.items():
        if w <= 0:
            continue
        if tag in ("modern", "traditional"):
            comps[f"style_{tag}"] = sum(tag in lex.get(c, {}).get("tags", []) for c in given) / len(given)
        elif tag == "soft":
            comps["style_soft"] = (feats["softness"] + feats["open_ratio"]) / 2
        elif tag == "bright":
            comps["style_bright"] = feats["brightness"]
    if liked:
        d = min(style_distance(feats, l) for l in liked)
        comps["liked_style"] = max(0.0, 1 - d)
    return comps


def generate(session: Session, req: GenerateRequest) -> dict[str, Any]:
    surname = normalize_name_text(req.surname_hangul)
    if not surname or not all(is_hangul_syllable(c) for c in surname):
        raise GenerationError("성씨 한글 표기가 올바르지 않습니다.")
    if req.syllables not in (1, 2, 3):
        raise GenerationError("이름 음절 수는 1~3입니다.")
    if req.name_type not in ("hanja", "hangul", "any"):
        raise GenerationError("name_type 은 hanja | hangul | any 입니다.")
    if req.sex not in ("m", "f", "n"):
        raise GenerationError("sex 는 m | f | n 입니다.")
    if not 1 <= req.count <= 200:
        raise GenerationError("count 는 1~200 입니다.")
    if any(w < 0 for w in req.style_tags.values()):
        raise GenerationError("가중치는 음수일 수 없습니다.")

    liked_given = [_strip_surname(normalize_name_text(n), surname) for n in req.liked_examples]
    liked_given = [n for n in liked_given if n and all(is_hangul_syllable(c) for c in n)]
    liked_feats = [style_features(n) for n in liked_given]

    removed: dict[str, int] = {}
    quarantined: list[dict] = []
    scored: list[dict] = []
    pool = _pool(req)
    # 1단계: 하드 필터 + 저비용 선호 점수로 상위 PRESCREEN_LIMIT 개만 남긴다 (결정론적 정렬)
    stage1 = []
    for given, path in pool:
        reason = _hard_filter(given, req, surname)
        if reason:
            removed[reason] = removed.get(reason, 0) + 1
            continue
        prefs = _preference_score(given, req, liked_feats)
        stage1.append((-(sum(prefs.values()) / len(prefs)) if prefs else 0.0, given, path, prefs))
    stage1.sort(key=lambda x: (x[0], x[1]))
    prescreen_cut = max(0, len(stage1) - PRESCREEN_LIMIT)
    # 2단계: 발음·부정 연상 분석
    for _, given, path, prefs in stage1[:PRESCREEN_LIMIT]:
        caution = la.caution_candidates(surname + given, len(surname))["candidates"]
        exact = [c for c in caution if c["match"] == "exact" and c["category"] in ("profanity", "insult")]
        if exact:
            quarantined.append({"given_hangul": given, "reason": "caution_exact", "caution": exact})
            continue
        phon = la.phonetic_features(surname + given, len(surname))
        pref_avg = sum(prefs.values()) / len(prefs) if prefs else None
        ease = phon["ease_score"] / 100
        gen_score = round((0.6 * pref_avg + 0.4 * ease) * 100 if pref_avg is not None else ease * 100, 1)
        scored.append({"given_hangul": given, "full_hangul": surname + given, "path": path,
                       "generation_score": gen_score,
                       "components": {**prefs, "phonetic_ease": ease},
                       "pronounced": phon["pronunciation"]["pronounced"],
                       "caution_similar": [c for c in caution if c not in exact]})
    scored.sort(key=lambda x: (-x["generation_score"], x["given_hangul"]))

    # 한자 가능 여부 — 한자 이름 요청 시 하드 필터, any 면 정보 표시
    selected: list[dict] = []
    first_count: dict[str, int] = {}
    last_count: dict[str, int] = {}
    skipped_diversity = 0
    skipped_no_hanja = 0
    hanja_cache: dict[str, bool] = {}
    for cand in scored:
        if len(selected) >= req.count:
            break
        g = cand["given_hangul"]
        if g in liked_given:
            skipped_diversity += 1
            continue
        if first_count.get(g[0], 0) >= req.max_same_first_syllable or (
                len(g) > 1 and last_count.get(g[-1], 0) >= req.max_same_last_syllable):
            skipped_diversity += 1
            continue
        if any(la.similarity({"given_hangul": g}, {"given_hangul": s["given_hangul"]})["combined"]
               >= req.diversity_threshold for s in selected):
            skipped_diversity += 1
            continue
        if req.name_type in ("hanja", "any"):
            ok = all(hanja_cache.setdefault(c, bool(candidates_for_syllable(session, c, limit=1))) for c in g)
            if req.name_type == "hanja" and not ok:
                skipped_no_hanja += 1
                continue
            cand["hanja_possible"] = ok
            if ok:
                rs = reverse_search(session, given_hangul=g, surname_hanja=req.surname_hanja,
                                    fixed=req.fixed_hanja, exclude_hanja=req.exclude_hanja,
                                    use_traditional=req.use_traditional, limit=3)
                cand["hanja_suggestions"] = rs["combinations"]["passed"] or rs["combinations"]["on_hold"]
                cand["hanja_counts"] = rs["counts"]
                if not cand["hanja_suggestions"] and req.name_type == "hanja":
                    skipped_no_hanja += 1
                    continue
                cand["official_gate"] = "pass" if rs["combinations"]["passed"] else (
                    "on_hold" if rs["combinations"]["on_hold"] else "fail")
        else:
            cand["hanja_possible"] = None
            cand["official_gate"] = "not_required"  # 한글 이름은 인명용 한자 판정 대상 아님
        first_count[g[0]] = first_count.get(g[0], 0) + 1
        last_count[g[-1]] = last_count.get(g[-1], 0) + 1
        selected.append(cand)

    on_hold = [c for c in selected if c.get("official_gate") == "on_hold"]
    passed = [c for c in selected if c.get("official_gate") in ("pass", "not_required")]
    return {
        "generator_version": GENERATOR_VERSION,
        "paths": {"rule_based": "enabled", "data_based": "limited (공개 이름 통계 미적재 — 한글 이름 예시·좋아한 이름 유사음만)",
                  "ai_based": "not_requested"},
        "passed": passed, "on_hold": on_hold,
        "quarantined": quarantined[:50],
        "stats": {"pool": len(pool), "removed_by_hard_filter": removed, "prescreen_cut": prescreen_cut,
                  "quarantined": len(quarantined),
                  "scored": len(scored), "skipped_for_diversity": skipped_diversity,
                  "skipped_no_hanja": skipped_no_hanja, "returned": len(selected)},
        "liked_examples_used": liked_given,
    }
