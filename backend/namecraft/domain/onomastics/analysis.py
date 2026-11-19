"""이름 언어 분석: 발음 특징·루브릭, 부정 연상 후보, 한자 뜻 주의, 연령별 참고, 로마자, 유사도.

각 결과에 status 를 붙인다:
  calculated        — 규칙으로 계산한 사실 (발음 추정, 음절·받침 수, 로마자 변환)
  subjective        — 루브릭/휴리스틱 평가 (발음 편의 점수, 연령별 참고)
  candidate         — 목록 대조로 찾은 '검토 권장' 후보 (판정 아님)
  not_available     — 근거 데이터 없음
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import yaml

from namecraft.config import REPO_ROOT
from namecraft.domain.hangul import decompose, jamo_string
from namecraft.domain.onomastics.pronunciation import pronounce

RULES_DIR = REPO_ROOT / "datasets" / "rules"
_PLAIN = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ", "ㅋ": "ㄱ", "ㅌ": "ㄷ", "ㅍ": "ㅂ", "ㅊ": "ㅈ"}
_TENSE_OR_ASP = set("ㄲㄸㅃㅆㅉㅋㅌㅍㅊ")


@lru_cache(maxsize=8)
def _rules(name: str) -> dict:
    return yaml.safe_load((RULES_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 발음 특징 + 루브릭

PHONETIC_RUBRIC_ID = "LANG.PHONETIC.RUBRIC.v0"
_RUBRIC = [  # (feature key, 감점, 설명)
    ("pronunciation_changed", 5, "표기와 발음이 달라 받아쓰기 혼동 가능"),
    ("tense_aspirated", 3, "된소리·거센소리 음절(개당)"),
    ("consonant_clusters", 4, "받침 뒤 자음이 이어지는 자음 충돌(개당)"),
    ("vowel_hiatus", 3, "모음이 연달아 나는 모음 충돌(개당)"),
    ("repeated_syllable", 6, "같은 음절 반복"),
    ("same_initial_run", 2, "같은 초성 연속(개당)"),
]


def phonetic_features(full: str, surname_len: int) -> dict[str, Any]:
    p = pronounce(full)
    syl = [decompose(c) for c in p.pronounced]
    given = full[surname_len:]
    feats = {
        "syllables": len(full),
        "batchim_count": sum(1 for s in syl if s[2]),
        "pronunciation_changed": int(p.changed),
        "tense_aspirated": sum(1 for s in syl if s[0] in _TENSE_OR_ASP),
        "consonant_clusters": sum(1 for a, b in zip(syl, syl[1:]) if a[2] and b[0] != "ㅇ"),
        "vowel_hiatus": sum(1 for a, b in zip(syl, syl[1:]) if not a[2] and b[0] == "ㅇ"),
        "repeated_syllable": int(len(set(given)) < len(given)),
        "same_initial_run": sum(1 for a, b in zip(syl, syl[1:]) if a[0] == b[0] and a[0] != "ㅇ"),
    }
    deductions = []
    score = 100
    for key, pts, desc in _RUBRIC:
        n = feats[key]
        if n:
            score -= pts * n
            deductions.append({"feature": key, "count": n, "points": pts * n, "description": desc})
    return {
        "pronunciation": p.to_dict(),
        "features": feats,
        "features_status": "calculated",
        "ease_score": max(score, 0),
        "ease_rubric": {"rule_id": PHONETIC_RUBRIC_ID, "deductions": deductions, "status": "subjective",
                        "note": "발음 편의 루브릭 v0 — 취향·지역에 따라 다르게 느낄 수 있음"},
    }


# ---------------------------------------------------------------- 부정 연상 후보

def _plainify(s: str) -> str:
    """된소리·거센소리를 예사소리로 바꾼 느슨한 비교용 문자열."""
    out = []
    for ch in s:
        try:
            i, m, f = decompose(ch)
        except ValueError:
            out.append(ch)
            continue
        out.append(_PLAIN.get(i, i) + m + f)
    return "".join(out)


@lru_cache(maxsize=256)
def _plain_word(word: str) -> str:
    return _plainify(word)


def caution_candidates(full: str, surname_len: int) -> dict[str, Any]:
    given = full[surname_len:]
    forms = {
        "given_written": given, "given_pronounced": pronounce(given).pronounced,
        "full_written": full, "full_pronounced": pronounce(full).pronounced,
    }
    hits = []
    plain_forms = {k: _plainify(v) for k, v in forms.items()}
    for w in _rules("caution-words-ko.yaml")["words"]:
        word = w["word"]
        plain_word = _plain_word(word)
        for form_key, form in forms.items():
            if w["match"] == "whole":
                exact = form == word and form_key.startswith("given")
                loose = False
            else:
                exact = word in form
                loose = not exact and len(word) >= 2 and plain_word in plain_forms[form_key]
            if exact or loose:
                hits.append({"word": word, "category": w["category"], "found_in": form_key,
                             "match": "exact" if exact else "similar_sound"})
    # 같은 단어가 여러 형태에서 걸리면 하나로 묶는다
    merged: dict[str, dict] = {}
    for h in hits:
        m = merged.setdefault(h["word"], {**h, "found_in": []})
        m["found_in"].append(h["found_in"])
        if h["match"] == "exact":
            m["match"] = "exact"
    return {"status": "candidate", "rule_id": _rules("caution-words-ko.yaml")["rule_id"],
            "candidates": list(merged.values()), "checked_forms": forms,
            "note": "소규모 목록 대조 결과입니다. 걸리지 않았다고 문제가 없다는 뜻은 아니며, 걸려도 부적합 판정이 아닙니다."}


# ---------------------------------------------------------------- 한자 뜻

def meaning_review(chars: list[dict]) -> dict[str, Any]:
    """chars: [{hanja, definition_en}] — Unihan 영어 풀이만 있음(한국어 훈 미적재)."""
    kw = _rules("meaning-caution-en.yaml")["keywords"]
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, kw)) + r")\b", re.I)
    items = []
    for c in chars:
        d = c.get("definition_en")
        hits = sorted({m.group(1).lower() for m in pattern.finditer(d or "")})
        items.append({"hanja": c.get("hanja"), "definition_en": d,
                      "definition_status": "unverified" if d else "not_available",
                      "caution_keywords": hits})
    return {"status": "candidate", "rule_id": _rules("meaning-caution-en.yaml")["rule_id"], "characters": items,
            "korean_meaning_status": "not_available",
            "combination_status": "not_available",
            "note": "한국어 뜻(훈)·의미 조합 평가는 국립국어원 자료 적재 또는 AI 해설(Phase 7) 이후 제공. 현재는 Unihan 영어 풀이만 참고."}


# ---------------------------------------------------------------- 연령별 사용성 (참고)

_CUTE_SYLLABLES = set("롱콩뽀쪼몽뿡쁨꽁뽕쭈쮸")


def usability_notes(full: str, surname_len: int, is_native_korean: bool | None = None) -> dict[str, Any]:
    given = full[surname_len:]
    notes = []
    if any(c in _CUTE_SYLLABLES for c in given):
        notes.append({"code": "childlike_syllable", "context": "adult",
                      "message": "아이 때 귀여운 느낌이 강한 음절이 있어 성인·공식 자리에서의 인상도 함께 고려해 보세요."})
    if len(given) >= 2 and len(set(given)) == 1:
        notes.append({"code": "reduplication", "context": "adult",
                      "message": "같은 음절을 반복하는 이름은 어린 인상을 줄 수 있습니다."})
    if len(given) >= 3:
        notes.append({"code": "long_given_name", "context": "documents",
                      "message": "이름이 3자 이상이면 일부 서식·시스템의 칸 길이를 확인하세요."})
    if len(given) == 1:
        notes.append({"code": "single_syllable", "context": "daily",
                      "message": "외자 이름은 부를 때 성과 함께 부르는 경우가 많습니다."})
    return {"status": "subjective", "notes": notes, "basis": "휴리스틱 참고 — 개인 취향과 사회 변화에 따라 다름"}


# ---------------------------------------------------------------- 로마자 (RR, 인명)

_RR_INI = dict(zip("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ",
                   ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]))
_RR_MED = dict(zip("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ",
                   ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
                    "yu", "eu", "ui", "i"]))
_RR_FIN = {"": "", "ㄱ": "k", "ㄲ": "k", "ㄳ": "k", "ㄴ": "n", "ㄵ": "n", "ㄶ": "n", "ㄷ": "t", "ㄹ": "l", "ㄺ": "k",
           "ㄻ": "m", "ㄼ": "l", "ㄽ": "l", "ㄾ": "l", "ㄿ": "p", "ㅀ": "l", "ㅁ": "m", "ㅂ": "p", "ㅄ": "p", "ㅅ": "t",
           "ㅆ": "t", "ㅇ": "ng", "ㅈ": "t", "ㅊ": "t", "ㅋ": "k", "ㅌ": "t", "ㅍ": "p", "ㅎ": "t"}


def rr_syllables(text: str) -> list[str]:
    out = []
    for idx, ch in enumerate(text):
        i, m, f = decompose(ch)
        ini = _RR_INI[i]
        # ㄹ받침 뒤 ㄹ초성은 ll
        if i == "ㄹ" and idx > 0 and decompose(text[idx - 1])[2] == "ㄹ":
            ini = "l"
        out.append(ini + _RR_MED[m] + _RR_FIN[f])
    return out


def romanize_name(surname: str, given: str) -> dict[str, Any]:
    data = _rules("romanization.yaml")
    g = rr_syllables(given)
    given_rr = "".join(g)
    # 인명: 음절 경계가 모호하면 붙임표 허용 (예: 지아 → Ji-a)
    ambiguous = any(not s or s[0] in "aeiouwy" for s in g[1:])
    given_display = "-".join(g).capitalize() if ambiguous else given_rr.capitalize()
    surname_rr = "".join(rr_syllables(surname)).capitalize()
    lowered = {given_rr.lower(), *g, surname_rr.lower(), *(c.lower() for c in data["surname_customary"].get(surname, []))}
    pitfalls = [p for p in data["english_pitfalls"] if p["text"] in lowered]
    return {
        "status": "calculated",
        "system": "국어의 로마자 표기법(RR), 인명 — 음운 변화 미반영",
        "surname_rr": surname_rr, "given_rr": given_display, "syllables": g,
        "surname_customary_examples": data["surname_customary"].get(surname, []),
        "english_pitfalls": {"status": "candidate", "items": pitfalls},
        "note": "여권 영문 성명은 외교부 기준(기존 표기·가족 표기 등)을 따르므로 이 결과는 참고용입니다.",
    }


# ---------------------------------------------------------------- 유사도 (REQ-LG-006)

def similarity(a: dict, b: dict) -> dict[str, Any]:
    """a, b: {"given_hangul", "given_hanja"?} — 이름(성 제외) 기준."""
    ga, gb = a["given_hangul"], b["given_hangul"]
    pa, pb = pronounce(ga).pronounced, pronounce(gb).pronounced
    syl_overlap = len(set(ga) & set(gb)) / len(set(ga) | set(gb))
    jamo_ratio = SequenceMatcher(None, jamo_string(pa), jamo_string(pb)).ratio()
    same_hanja = bool(a.get("given_hanja")) and a.get("given_hanja") == b.get("given_hanja")
    structure = int(len(ga) == len(gb)) * 0.5 + int(
        [bool(decompose(c)[2]) for c in ga] == [bool(decompose(c)[2]) for c in gb]) * 0.5
    combined = round(0.45 * jamo_ratio + 0.35 * syl_overlap + 0.2 * structure, 3)
    return {
        "same_written": ga == gb, "same_pronounced": pa == pb, "same_hanja": same_hanja,
        "syllable_overlap": round(syl_overlap, 3), "jamo_similarity": round(jamo_ratio, 3),
        "structure_similarity": structure, "combined": combined,
        "is_duplicate": ga == gb and (same_hanja or not (a.get("given_hanja") or b.get("given_hanja"))),
        "status": "calculated", "rule_id": "LANG.SIMILARITY.v1",
    }
