"""한글 음절 분해 (발음·음령오행용)."""

from __future__ import annotations

INITIALS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
MEDIALS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
FINALS = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ",
          "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
_TENSE_TO_PLAIN = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ"}


def decompose(syllable: str) -> tuple[str, str, str]:
    code = ord(syllable) - 0xAC00
    if len(syllable) != 1 or not 0 <= code < 11172:
        raise ValueError(f"한글 음절이 아닙니다: {syllable!r}")
    return INITIALS[code // 588], MEDIALS[(code % 588) // 28], FINALS[code % 28]


def initial_consonant(syllable: str, *, plain: bool = True) -> str:
    ini = decompose(syllable)[0]
    return _TENSE_TO_PLAIN.get(ini, ini) if plain else ini
