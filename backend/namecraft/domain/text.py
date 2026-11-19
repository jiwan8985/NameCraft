"""한글·한자 텍스트 정규화 (기획서 §5, REQ-IN-001).

주의: 유니코드 NFC 정규화는 CJK 호환 한자(U+F900–U+FAFF, U+2F800–U+2FA1F)를
통합 한자로 바꿔 버린다(예: U+F9E1 李(이) → U+674E 李). 한국 인명용 한자는 호환 한자로
독음을 구분하는 경우가 있으므로, 호환 한자는 **절대 NFC로 접지 않고** 원래 코드포인트를 보존한다.
"""

from __future__ import annotations

import unicodedata

_COMPAT_RANGES = ((0xF900, 0xFAFF), (0x2F800, 0x2FA1F))
_UNIFIED_RANGES = (
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # Ext A
    (0x20000, 0x2A6DF),  # Ext B
    (0x2A700, 0x2EE5F),  # Ext C–F, I
    (0x30000, 0x323AF),  # Ext G–H
)


def _in(cp: int, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def is_compat_hanja(ch: str) -> bool:
    return len(ch) == 1 and _in(ord(ch), _COMPAT_RANGES)


def is_hanja(ch: str) -> bool:
    return len(ch) == 1 and (_in(ord(ch), _UNIFIED_RANGES) or _in(ord(ch), _COMPAT_RANGES))


def is_hangul_syllable(ch: str) -> bool:
    return len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3


def codepoint(ch: str) -> str:
    return f"U+{ord(ch):04X}"


def char_from_codepoint(cp: str) -> str:
    return chr(int(cp.removeprefix("U+"), 16))


def normalize_name_text(text: str) -> str:
    """앞뒤 공백 제거 + 한글 등은 NFC, 호환 한자는 원형 보존."""
    out: list[str] = []
    buf: list[str] = []
    for ch in text.strip():
        if is_compat_hanja(ch):
            if buf:
                out.append(unicodedata.normalize("NFC", "".join(buf)))
                buf = []
            out.append(ch)
        else:
            buf.append(ch)
    if buf:
        out.append(unicodedata.normalize("NFC", "".join(buf)))
    return "".join(out)


def codepoint_sequence(text: str) -> list[str]:
    return [codepoint(ch) for ch in normalize_name_text(text)]
