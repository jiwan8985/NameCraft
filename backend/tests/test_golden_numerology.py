"""datasets/golden-tests/numerology.yaml 실행기."""

from __future__ import annotations

import pytest
import yaml

from namecraft.config import REPO_ROOT
from namecraft.domain.numerology.core import (
    CharInput, NumerologyOptions, analyze, eumryeong, four_gyeok, reduce81, yinyang,
)
from namecraft.domain.numerology.elements import digit_element
from namecraft.services.numerology import analyze_name

pytestmark = pytest.mark.golden

DOC = yaml.safe_load((REPO_ROOT / "datasets" / "golden-tests" / "numerology.yaml").read_text(encoding="utf-8"))
CASES = [pytest.param(c, id=c["id"]) for c in DOC["cases"]]


@pytest.mark.parametrize("case", CASES)
def test_golden(case, lexicon_session):
    if case["status"] == "pending":
        pytest.skip("pending")
    i, exp = case["input"], case["expected"]
    opts = i.get("options", {})

    if "surname" in i:  # 가상 정수 획수 입력
        got = four_gyeok(i["surname"], i["given"], virtual=opts.get("single_name_virtual_stroke", "none"))
        assert got == exp
    elif "value" in i:
        assert reduce81(i["value"]) == exp["reduced"]
    elif "values" in i:
        assert [digit_element(v) for v in i["values"]] == exp["elements"]
    elif "strokes" in i:
        assert yinyang(i["strokes"]) == exp["pattern"]
    elif "hangul" in i:
        for school, want in exp.items():
            assert eumryeong(i["hangul"], school) == want
    elif "given_hangul" in i:
        r = analyze_name(lexicon_session, surname_hangul=i["surname_hangul"], surname_hanja=i.get("surname_hanja"),
                         given_hangul=i["given_hangul"], given_hanja=i.get("given_hanja"),
                         opts=NumerologyOptions(**opts))
        if "numerology" in exp:
            assert r["applicability"]["numerology"] == exp["numerology"]
            assert r["applicability"]["eumryeong"] == exp["eumryeong"]
            assert "calc" not in r and "trad" not in r  # 임의 계산 금지 (기획서 §23)
            return
        if "first_given_strokes" in exp:
            surname_len = len(i["surname_hangul"])
            assert r["characters"][surname_len]["strokes"] == exp["first_given_strokes"]
            return
        assert [c["strokes"] for c in r["characters"]] == exp["strokes"]
        fg = r["calc"]["four_gyeok"]
        assert {k: fg[k]["value"] for k in ("won", "hyeong", "i", "jeong")} == \
               {k: exp[k] for k in ("won", "hyeong", "i", "jeong")}
    else:  # pragma: no cover
        pytest.fail("unknown case shape")


def test_luck_table_complete_and_disputes_marked():
    from namecraft.domain.numerology.core import luck_of, luck_table

    t = luck_table()
    assert t["status"] == "source_check_pending"
    assert set(t["numbers"]) == set(range(1, 82))
    assert luck_of(95)["reduced"] == 15  # 환원 후 조회
    assert luck_of(27)["disputed"] and luck_of(27)["alternatives"]
    assert not luck_of(21)["disputed"]


def test_hangul_only_never_computes_strokes():
    r = analyze([CharInput("심", "沈", modern_strokes=7, original_strokes=8)], [CharInput("초"), CharInput("롱")],
                NumerologyOptions())
    assert r["applicability"]["numerology"] == "not_applicable"
    assert r["eumryeong"]["elements"] == ["金", "金", "火"]
