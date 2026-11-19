"""종합 랭킹 (기획서 §10, REQ-RK-001~005) + 취향 학습 (§9, REQ-AI-001/002).

- 가중치: 음수 불가, 합계 100%로 정규화. 근거 없는 항목은 N/A → 제외 후 재정규화 + `incomplete_data` 경고 (0점 대체 금지).
- 유효성(공식 한자·하드 조건)은 점수에 섞지 않고 `gate: pass | fail | unknown` 로 별도 표시.
- 취향 학습은 '희소성·개인 선호' 항목만 조정하며 법적 판정·전통 계산을 바꾸지 않는다.
"""

from __future__ import annotations

from typing import Any

from namecraft.domain.numerology.core import NumerologyOptions
from namecraft.services.generation import style_distance, style_features
from namecraft.services.lexicon import OFFICIAL_NOT_LISTED, OFFICIAL_VERIFIED, official_status
from namecraft.services.name_analysis import analyze_full
from namecraft.domain.text import codepoint

RANKING_VERSION = "rank-0.1.0"
DEFAULT_WEIGHTS = {"phonetic": 25, "meaning": 20, "saju": 20, "numerology": 15, "usability": 15, "preference": 5}
CATEGORY_LABELS = {"phonetic": "발음·어감", "meaning": "이름 의미", "saju": "전통 사주·오행 해석",
                   "numerology": "전통 획수·수리 해석", "usability": "현대적 사용성", "preference": "희소성·개인 선호"}
CATEGORY_NATURE = {"phonetic": "calculated+subjective", "meaning": "candidate", "saju": "traditional_interpretation",
                   "numerology": "traditional_interpretation", "usability": "subjective", "preference": "subjective"}


class RankingError(ValueError):
    pass


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    if set(w) - set(DEFAULT_WEIGHTS):
        raise RankingError(f"알 수 없는 항목: {sorted(set(w) - set(DEFAULT_WEIGHTS))}")
    if any(v < 0 for v in w.values()):
        raise RankingError("가중치는 음수일 수 없습니다.")
    total = sum(w.values())
    if total <= 0:
        raise RankingError("가중치 합계는 0보다 커야 합니다.")
    return {k: v / total for k, v in w.items()}


# ---------------------------------------------------------------- 취향 학습

def preference_profile(liked: list[str], disliked: list[str]) -> dict[str, Any]:
    """좋아요/싫어요 이름(성 제외)으로 결정론적 선호 프로필 생성."""
    def syl_counts(names):
        c: dict[str, int] = {}
        for n in names:
            for s in set(n):
                c[s] = c.get(s, 0) + 1
        return c
    return {"liked": liked, "disliked": disliked,
            "liked_features": [style_features(n) for n in liked],
            "disliked_features": [style_features(n) for n in disliked],
            "liked_syllables": syl_counts(liked), "disliked_syllables": syl_counts(disliked)}


def preference_score(given: str, profile: dict | None) -> float | None:
    if not profile or not (profile["liked"] or profile["disliked"]):
        return None
    f = style_features(given)
    like = 1 - min((style_distance(f, x) for x in profile["liked_features"]), default=1.0)
    dislike = 1 - min((style_distance(f, x) for x in profile["disliked_features"]), default=1.0)
    syl_bonus = sum(profile["liked_syllables"].get(s, 0) for s in set(given)) / max(1, len(profile["liked"]))
    syl_malus = sum(profile["disliked_syllables"].get(s, 0) for s in set(given)) / max(1, len(profile["disliked"]))
    raw = 0.5 + 0.35 * (max(0.0, like) - max(0.0, dislike)) + 0.15 * (min(1, syl_bonus) - min(1, syl_malus))
    return round(max(0.0, min(1.0, raw)) * 100, 1)


# ---------------------------------------------------------------- 항목 점수

def _category_scores(a: dict, profile: dict | None, use_saju: bool) -> dict[str, dict]:
    out: dict[str, dict] = {}
    out["phonetic"] = {"score": a["phonetics"]["ease_score"], "basis": "발음 편의 루브릭 v0"}

    m = a["meaning"]
    if m.get("status") == "not_applicable":
        out["meaning"] = {"score": None, "basis": "한자 없음 — 근거 자료 없음"}
    else:
        has_caution = any(c["caution_keywords"] for c in m["characters"])
        out["meaning"] = {"score": 40.0 if has_caution else 70.0,
                          "basis": "영어 풀이 주의 키워드 유무만 반영(한국어 뜻 미적재) — 상한 70"}

    out["saju"] = {"score": None, "basis": "사주 해석 항목 미사용(학파 규칙 미정·출생정보 연동 Phase 9)" if not use_saju
                   else "사주 해석 프로필 미구현"}

    num = a["numerology"]
    if num["applicability"]["numerology"] == "applicable":
        val = {"good": 1.0, "half": 0.5, "bad": 0.0}
        lucks = num["trad"]["luck81"].values()
        luck = sum(val[x["class"]] for x in lucks) / 4
        yy = 1.0 if num["trad"]["yinyang"]["value"] == "조화" else 0.0
        out["numerology"] = {"score": round((0.8 * luck + 0.2 * yy) * 100, 1),
                             "basis": "81수리(길1·반길0.5·흉0) 80% + 음양 조화 20% — 전통 해석 · 출처 대조 전",
                             "disputed": [k for k, x in num["trad"]["luck81"].items() if x["disputed"]]}
    else:
        out["numerology"] = {"score": None, "basis": num["applicability"].get("reason", "적용 불가")}

    notes = [n for n in a["usability"]["notes"] if n["context"] in ("adult", "documents")]
    pit = a["romanization"]["english_pitfalls"]["items"]
    caution_n = len(a["caution"]["candidates"])
    out["usability"] = {"score": max(0.0, 100.0 - 15 * len(notes) - 15 * len(pit) - 20 * caution_n),
                        "basis": "연령·서식 참고 사항, 영어권 오해 철자, 부정 연상 후보 개수 감점"}

    ps = preference_score(a["name"]["given_hangul"], profile)
    out["preference"] = {"score": ps, "basis": "좋아요/싫어요 반응 기반 취향 프로필 (희소성 통계 미적재)"
                         if ps is not None else "반응 기록 없음"}
    return out


def official_gate(session, given_hanja: str | None, given_hangul: str) -> str:
    if not given_hanja:
        return "pass"  # 한글 이름: 인명용 한자 판정 대상 아님(출생신고 점검은 Phase 10)
    statuses = [official_status(session, codepoint(c), given_hangul[i])["status"] for i, c in enumerate(given_hanja)]
    if OFFICIAL_NOT_LISTED in statuses:
        return "fail"
    return "pass" if all(s == OFFICIAL_VERIFIED for s in statuses) else "unknown"


def rank_names(session, *, surname_hangul: str, surname_hanja: str | None, names: list[dict],
               weights: dict | None = None, profile: dict | None = None, use_saju: bool = False,
               numerology_options: NumerologyOptions | None = None) -> dict[str, Any]:
    w = normalize_weights(weights)
    rows = []
    for n in names:
        a = analyze_full(session, surname_hangul=surname_hangul, surname_hanja=surname_hanja,
                         given_hangul=n["given_hangul"], given_hanja=n.get("given_hanja") or None,
                         numerology_options=numerology_options)
        cats = _category_scores(a, profile, use_saju)
        avail = {k: w[k] for k, v in cats.items() if v["score"] is not None and w[k] > 0}
        tw = sum(avail.values())
        total = round(sum(cats[k]["score"] * wk for k, wk in avail.items()) / tw, 1) if tw else None
        missing = [k for k in cats if cats[k]["score"] is None and w[k] > 0]
        rows.append({
            **{k: n.get(k) for k in ("id", "given_hangul", "given_hanja", "source", "status")},
            "full_hangul": a["name"]["full_hangul"],
            "gate": {"official_hanja": official_gate(session, n.get("given_hanja") or None, n["given_hangul"]),
                     "caution": "review" if a["caution"]["candidates"] else "none"},
            "overall": total,
            "categories": {k: {**v, "label": CATEGORY_LABELS[k], "nature": CATEGORY_NATURE[k],
                               "weight": round(w[k], 4), "effective_weight": round(avail.get(k, 0) / tw, 4) if tw else 0}
                           for k, v in cats.items()},
            "incomplete": missing,
            "confidence": {"data_verification": "official" if n.get("given_hanja") and official_gate(
                                session, n.get("given_hanja"), n["given_hangul"]) == "pass" else "unverified",
                           "reproducible": True,
                           "school_agreement": a["numerology"]["eumryeong"]["school_agreement"],
                           "ai_subjective": bool(n.get("ai_reason"))},
            "ai_reason": n.get("ai_reason"),
        })
    return {"ranking_version": RANKING_VERSION, "weights_normalized": w, "items": rows}


SORT_KEYS = {"overall", *DEFAULT_WEIGHTS}


def sort_items(items: list[dict], by: str) -> list[dict]:
    if by not in SORT_KEYS:
        raise RankingError(f"정렬 기준: {sorted(SORT_KEYS)}")
    def key(r):
        v = r["overall"] if by == "overall" else r["categories"][by]["score"]
        return (v is None, -(v or 0), r["given_hangul"], r.get("given_hanja") or "")
    return sorted(items, key=key)

