"""REQ-IN-001: Unicode 정규화 — 호환 한자 보존 (§22.2 '호환한자')."""

import unicodedata

from hypothesis import given, strategies as st

from namecraft.domain.text import codepoint, codepoint_sequence, is_compat_hanja, is_hanja, normalize_name_text


def test_nfc_would_destroy_compat_hanja_but_we_do_not():
    assert unicodedata.normalize("NFC", "李") == "李"  # 위험 확인
    assert normalize_name_text("李") == "李"
    assert codepoint_sequence("沈李") == ["U+6C88", "U+F9E1"]


def test_hangul_jamo_composed():
    assert normalize_name_text("심 ") == "심"


def test_mixed_text_keeps_compat_and_composes_hangul():
    assert normalize_name_text("심沈") == "심沈"


def test_classifiers():
    assert is_hanja("沈") and is_hanja("沈") and is_compat_hanja("沈")
    assert not is_hanja("심") and not is_compat_hanja("沈")
    assert codepoint("沈") == "U+6C88"


@given(st.text(alphabet=st.characters(min_codepoint=0xF900, max_codepoint=0xFAD9), max_size=6))
def test_compat_ideographs_never_folded(s):
    assert normalize_name_text(s) == s.strip()
