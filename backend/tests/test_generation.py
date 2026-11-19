"""Phase 6 게이트: AI 없이 후보 생성 · 무효 후보 차단 · 역검색 · 대체 한자 · 다양성 · 결정론."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st

from namecraft.adapters.importers.scourt_hanja import import_official_csv
from namecraft.domain.onomastics.analysis import similarity
from namecraft.services.generation import GenerateRequest, generate
from namecraft.services.reverse_search import alternative_hanja, reverse_search

LIKED = ["심수정", "심지수", "심초롱", "심은하", "심하은", "심유리", "심혜리", "심지아"]


def _all(r):
    return r["passed"] + r["on_hold"]


def test_generates_without_ai_and_is_deterministic(lexicon_session):
    req = GenerateRequest(surname_hangul="심", surname_hanja="沈", sex="f", count=15, liked_examples=LIKED,
                          name_type="hangul")
    a, b = generate(lexicon_session, req), generate(lexicon_session, req)
    names = [c["given_hangul"] for c in _all(a)]
    assert len(names) == 15 and names == [c["given_hangul"] for c in _all(b)]
    assert a["paths"]["ai_based"] == "not_requested"
    assert all(c["official_gate"] == "not_required" for c in _all(a))


def test_no_duplicates_and_liked_examples_not_repeated(lexicon_session):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="심", count=40, liked_examples=LIKED,
                                                  name_type="hangul"))
    names = [c["given_hangul"] for c in _all(r)]
    assert len(names) == len(set(names))
    assert not set(names) & {n[1:] for n in LIKED}


def test_diversity_threshold_respected(lexicon_session):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="김", count=25, name_type="hangul",
                                                  diversity_threshold=0.7))
    names = [c["given_hangul"] for c in _all(r)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert similarity({"given_hangul": a}, {"given_hangul": b})["combined"] < 0.7
    firsts = [n[0] for n in names]
    assert max(firsts.count(f) for f in set(firsts)) <= 3


def test_hard_filters(lexicon_session):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="김", count=20, name_type="hangul",
                                                  fixed_syllable={1: "준"}, exclude_initials=["ㄷ"],
                                                  exclude_syllables=["우"], exclude_names=["김재준"]))
    names = [c["given_hangul"] for c in _all(r)]
    assert names and all(n[1] == "준" for n in names)
    assert not any(n.startswith(("다", "대", "도", "동")) for n in names)
    assert "우준" not in names and "재준" not in names
    assert r["stats"]["removed_by_hard_filter"]["fixed_syllable"] > 0


def test_sex_is_preference_not_restriction(lexicon_session):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="김", sex="m", count=10, name_type="hangul",
                                                  include_syllables=["아"]))
    assert _all(r)  # 여성 경향 음절 '아'를 포함해도 제거되지 않음


def test_hanja_names_require_name_reading_hanja_and_are_on_hold(lexicon_session):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="심", surname_hanja="沈", count=5,
                                                  include_syllables=["지"], name_type="hanja"))
    assert r["passed"] == [] and r["on_hold"]  # 공식 자료 미적재 → 보류
    for c in r["on_hold"]:
        assert c["official_gate"] == "on_hold" and c["hanja_suggestions"]


def test_quarantine_exact_profanity(lexicon_session, monkeypatch):
    from namecraft.services import generation as g

    lex = {"syllables": {"바": {"position": "first", "gender": "n", "tags": []},
                         "보": {"position": "second", "gender": "n", "tags": []},
                         "나": {"position": "second", "gender": "n", "tags": []}}, "native_names": []}
    monkeypatch.setattr(g, "lexicon", lambda: lex)
    r = generate(lexicon_session, GenerateRequest(surname_hangul="김", name_type="hangul", count=5))
    assert [q["given_hangul"] for q in r["quarantined"]] == ["바보"]
    assert [c["given_hangul"] for c in _all(r)] == ["바나"]


def test_reverse_search_buckets_and_scores(lexicon_session):
    r = reverse_search(lexicon_session, given_hangul="지아", surname_hanja="沈")
    assert r["counts"]["passed"] == 0 and r["counts"]["on_hold"] > 0
    top = r["combinations"]["on_hold"][0]
    assert set(top["components"]) == {"common_hanja", "no_meaning_caution", "luck81", "yinyang_balance"}
    assert top["traditional"]["status"] == "source_check_pending"
    # 뜻 주의 키워드(굶주릴 餓)가 있는 조합은 만점이 아니다
    for c in r["combinations"]["on_hold"]:
        if "餓" in c["hanja"]:
            assert c["components"]["no_meaning_caution"] == 0.0


def test_reverse_search_without_surname_hanja_renormalizes(lexicon_session):
    r = reverse_search(lexicon_session, given_hangul="지아")
    top = r["combinations"]["on_hold"][0]
    assert set(top["not_available"]) == {"luck81", "yinyang_balance"}
    assert set(top["weights_used"]) == {"common_hanja", "no_meaning_caution"}


def test_reverse_search_impossible_syllable(lexicon_session):
    r = reverse_search(lexicon_session, given_hangul="뷁")
    assert r["impossible_syllables"] == ["뷁"] and r["hangul_only_possible"]


def test_official_data_moves_combinations_to_passed_or_rejected(lexicon_session, tmp_path):
    f = tmp_path / "official.csv"
    f.write_text("hanja,reading,effective_date,legal_basis\n智,지,2024-01-01,TEST\n雅,아,2024-01-01,TEST\n",
                 encoding="utf-8")
    import_official_csv(lexicon_session, f, is_sample=False)
    r = reverse_search(lexicon_session, given_hangul="지아", surname_hanja="沈", limit=200)
    assert [c["hanja"] for c in r["combinations"]["passed"]] == ["智雅"]
    assert r["counts"]["on_hold"] == 0 and r["counts"]["rejected"] > 0  # 공식 미수록 글자 포함 조합은 차단


def test_alternative_hanja(lexicon_session):
    a = alternative_hanja(lexicon_session, given_hangul="지아", given_hanja="智雅", surname_hanja="沈")
    assert len(a["positions"]) == 2
    for p in a["positions"]:
        for alt in p["alternatives"]:
            assert alt["optimization_score"] > a["current"]["optimization_score"]


@given(st.sampled_from(["m", "f", "n"]), st.integers(min_value=1, max_value=3))
@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])  # 읽기 전용
def test_property_constraints_always_hold(lexicon_session, sex, syl):
    r = generate(lexicon_session, GenerateRequest(surname_hangul="이", sex=sex, syllables=syl, count=10,
                                                  name_type="hangul", exclude_initials=["ㅎ"]))
    for c in _all(r):
        assert len(c["given_hangul"]) == syl and not c["given_hangul"].startswith("이")


def test_any_mode_never_drops_candidates_silently(lexicon_session):
    """회귀: name_type=any 에서 한자 조합이 없는 후보가 결과 버킷에서 사라지던 문제."""
    r = generate(lexicon_session, GenerateRequest(surname_hangul="심", surname_hanja="沈", count=10, name_type="any"))
    assert r["stats"]["returned"] == len(r["passed"]) + len(r["on_hold"]) == 10
    assert any(c["official_gate"] == "not_required" and c["hanja_possible"] is False for c in r["passed"])
