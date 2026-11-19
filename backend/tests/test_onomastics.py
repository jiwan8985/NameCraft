"""Phase 5: 발음·부정 연상·의미·사용성·로마자·유사도. 게이트: '명확한 판정/미확인 구분'."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from namecraft.config import REPO_ROOT
from namecraft.domain.onomastics import analysis as la
from namecraft.domain.onomastics.claims import find_forbidden_claims
from namecraft.domain.onomastics.pronunciation import pronounce

PRON = yaml.safe_load((REPO_ROOT / "datasets/golden-tests/pronunciation.yaml").read_text(encoding="utf-8"))


@pytest.mark.golden
@pytest.mark.parametrize("case", [pytest.param(c, id=c["id"]) for c in PRON["cases"]])
def test_pronunciation_golden(case):
    p = pronounce(case["input"])
    assert p.pronounced == case["expected"]
    if case["rule"]:
        assert case["rule"] in {r["rule_id"] for r in p.rules}


def test_every_section_has_explicit_status():
    r = {"phonetics": la.phonetic_features("심지아", 1), "caution": la.caution_candidates("심지아", 1),
         "meaning": la.meaning_review([{"hanja": "智", "definition_en": "wisdom, knowledge"}]),
         "usability": la.usability_notes("심지아", 1), "romanization": la.romanize_name("심", "지아")}
    assert r["phonetics"]["features_status"] == "calculated"
    assert r["phonetics"]["ease_rubric"]["status"] == "subjective"
    assert r["phonetics"]["pronunciation"]["status"] == "calculated"
    assert r["caution"]["status"] == "candidate"
    assert r["meaning"]["status"] == "candidate" and r["meaning"]["korean_meaning_status"] == "not_available"
    assert r["usability"]["status"] == "subjective"
    assert r["romanization"]["status"] == "calculated"
    assert r["romanization"]["english_pitfalls"]["status"] == "candidate"


def test_caution_detects_exact_and_similar_sound_but_not_innocent_words():
    assert [c["word"] for c in la.caution_candidates("김똥이", 1)["candidates"]] == ["똥"]
    sim = la.caution_candidates("이씨발", 1)["candidates"]
    assert {c["word"] for c in sim} >= {"씨발", "시발"}
    assert next(c for c in sim if c["word"] == "시발")["match"] == "similar_sound"
    assert la.caution_candidates("이신발", 1)["candidates"] == []  # 신발(신발)은 비속어 아님
    assert la.caution_candidates("심지아", 1)["candidates"] == []
    # whole 매칭 단어는 이름 전체가 같을 때만
    assert la.caution_candidates("김변", 1)["candidates"][0]["word"] == "변"
    assert la.caution_candidates("김변호", 1)["candidates"] == []


def test_caution_checks_pronounced_form():
    # 받침 연음으로 발음상 나타나는 경우: 석이 → [서기] 등은 목록에 없음. 대신 발음형이 검사 대상인지 확인
    forms = la.caution_candidates("박민준", 1)["checked_forms"]
    assert forms["full_pronounced"] == "방민준"


def test_meaning_keywords_word_boundary():
    r = la.meaning_review([{"hanja": "死", "definition_en": "die; dead; death"},
                           {"hanja": "智", "definition_en": "wisdom, knowledge, intelligence"},
                           {"hanja": "X", "definition_en": None}])
    kws = [c["caution_keywords"] for c in r["characters"]]
    assert kws[0] == ["dead", "death", "die"] and kws[1] == [] and r["characters"][2]["definition_status"] == "not_available"


def test_phonetic_rubric_is_deterministic_and_explained():
    a = la.phonetic_features("최지지", 1)
    assert a == la.phonetic_features("최지지", 1)
    feats = {d["feature"] for d in a["ease_rubric"]["deductions"]}
    assert {"repeated_syllable", "same_initial_run"} <= feats
    assert a["ease_score"] == 100 - sum(d["points"] for d in a["ease_rubric"]["deductions"])


def test_usability_notes():
    codes = lambda full, n=1: {x["code"] for x in la.usability_notes(full, n)["notes"]}  # noqa: E731
    assert "childlike_syllable" in codes("심초롱")
    assert "reduplication" in codes("최지지")
    assert "single_syllable" in codes("김민")
    assert "long_given_name" in codes("이하늘별")


def test_romanization_rr_rules():
    assert la.romanize_name("심", "지아")["given_rr"] == "Ji-a"
    assert la.romanize_name("최", "설란")["given_rr"] == "Seollan"
    assert la.romanize_name("김", "민준")["given_rr"] == "Minjun"  # 인명은 음운 변화 미반영
    r = la.romanize_name("이", "동현")
    assert r["given_rr"] == "Donghyeon" and r["english_pitfalls"]["items"][0]["text"] == "dong"
    assert la.romanize_name("이", "수아")["surname_customary_examples"] == ["Lee", "Yi", "Rhee"]


def test_similarity_and_duplicates():
    s = la.similarity({"given_hangul": "지아"}, {"given_hangul": "지아"})
    assert s["same_written"] and s["is_duplicate"] and s["combined"] == 1.0
    diff_hanja = la.similarity({"given_hangul": "지아", "given_hanja": "智雅"}, {"given_hangul": "지아", "given_hanja": "知娥"})
    assert diff_hanja["same_written"] and not diff_hanja["is_duplicate"]
    near = la.similarity({"given_hangul": "지아"}, {"given_hangul": "지안"})["combined"]
    far = la.similarity({"given_hangul": "지아"}, {"given_hangul": "수정"})["combined"]
    assert near > far


def test_forbidden_claims_lint():
    assert find_forbidden_claims("이 이름은 반드시 성공합니다")
    assert find_forbidden_claims("건강을 보장합니다")
    assert find_forbidden_claims("운명을 결정합니다")
    assert not find_forbidden_claims("이름이 건강·성공·운명을 결정하지 않습니다.")
    assert not find_forbidden_claims("전통 해석이며 과학적 근거가 없습니다.")


def test_project_messages_contain_no_forbidden_claims():
    roots = [REPO_ROOT / "backend" / "namecraft", REPO_ROOT / "apps" / "api", REPO_ROOT / "apps" / "web" / "src",
             REPO_ROOT / "datasets" / "rules"]
    offenders = []
    for root in roots:
        for f in root.rglob("*"):
            if f.suffix in {".py", ".ts", ".tsx", ".yaml"} and "node_modules" not in f.parts \
                    and f.name != "forbidden-claims.yaml":
                hits = find_forbidden_claims(f.read_text(encoding="utf-8"))
                if hits:
                    offenders.append((str(Path(f).relative_to(REPO_ROOT)), hits))
    assert offenders == []
