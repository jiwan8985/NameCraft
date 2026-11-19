"""표준 발음 추정 — 표준발음법(국립국어원 「표준어 규정」 제2부)의 주요 규칙을 이름에 적용.

결과 성격: calculated(규칙 기반 추정). 실제 화자 발음·방언·개인차는 반영하지 않는다.
지원 규칙 (rule_id):
  PRON.LINK      연음 (받침 + ㅇ초성)                       예: 김연아 → [기며나]
  PRON.PALATAL   구개음화 (ㄷ·ㅌ + 이)                       예: 굳이 → [구지]
  PRON.H_DROP    ㅎ 탈락 (ㅎ받침 + 모음)                     예: 놓아 → [노아]
  PRON.ASPIRATE  거센소리되기 (ㅎ ↔ ㄱ·ㄷ·ㅂ·ㅈ)            예: 입학 → [이팍]
  PRON.CODA      받침 대표음 (7종성)
  PRON.NASAL     비음화 (ㄱ·ㄷ·ㅂ + ㄴ·ㅁ, ㅁ·ㅇ + ㄹ→ㄴ)      예: 국민 → [궁민], 침략 → [침냑], 백로 → [뱅노]
  PRON.LIQUID    유음화 (ㄴ+ㄹ, ㄹ+ㄴ → ㄹㄹ)               예: 신라 → [실라]
  PRON.TENSE     된소리되기 (ㄱ·ㄷ·ㅂ 받침 + ㄱ·ㄷ·ㅂ·ㅅ·ㅈ) 예: 박지 → [박찌]
  PRON.UI        자음 뒤 'ㅢ' → [ㅣ] (제5항 다만 3)           예: 희망 → [히망]
미지원: ㄴ 첨가, 사잇소리, 겹받침 세부 규칙(이름에서 드묾) — 결과에 경고로 표시.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from namecraft.domain.hangul import compose, decompose

_CODA_REP = {"ㄲ": "ㄱ", "ㅋ": "ㄱ", "ㄳ": "ㄱ", "ㄺ": "ㄱ", "ㅅ": "ㄷ", "ㅆ": "ㄷ", "ㅈ": "ㄷ", "ㅊ": "ㄷ",
             "ㅌ": "ㄷ", "ㅎ": "ㄷ", "ㅍ": "ㅂ", "ㅄ": "ㅂ", "ㄿ": "ㅂ", "ㄵ": "ㄴ", "ㄶ": "ㄴ", "ㄼ": "ㄹ",
             "ㄽ": "ㄹ", "ㄾ": "ㄹ", "ㅀ": "ㄹ", "ㄻ": "ㅁ"}
_CLUSTER_SPLIT = {"ㄳ": ("ㄱ", "ㅅ"), "ㄵ": ("ㄴ", "ㅈ"), "ㄶ": ("ㄴ", "ㅎ"), "ㄺ": ("ㄹ", "ㄱ"), "ㄻ": ("ㄹ", "ㅁ"),
                  "ㄼ": ("ㄹ", "ㅂ"), "ㄽ": ("ㄹ", "ㅅ"), "ㄾ": ("ㄹ", "ㅌ"), "ㄿ": ("ㄹ", "ㅍ"), "ㅀ": ("ㄹ", "ㅎ"),
                  "ㅄ": ("ㅂ", "ㅅ")}
_ASPIRATE = {"ㄱ": "ㅋ", "ㄷ": "ㅌ", "ㅂ": "ㅍ", "ㅈ": "ㅊ"}
_TENSE = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}
_NASAL = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}
_DOUBLE_CODA = {"ㄲ", "ㅆ"}


@dataclass
class Pronunciation:
    written: str
    pronounced: str
    rules: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.written != self.pronounced

    def to_dict(self) -> dict:
        return {"written": self.written, "pronounced": self.pronounced, "changed": self.changed,
                "rules": self.rules, "warnings": self.warnings, "status": "calculated",
                "basis": "표준발음법 주요 규칙 기반 추정"}


def pronounce(text: str) -> Pronunciation:
    syl = [list(decompose(ch)) for ch in text]  # [initial, medial, final]
    rules: list[dict] = []
    warnings: list[str] = []

    def log(rule_id: str, i: int, desc: str):
        rules.append({"rule_id": rule_id, "position": i, "description": desc})

    for i in range(len(syl) - 1):
        cur, nxt = syl[i], syl[i + 1]
        f, ini = cur[2], nxt[0]
        if not f:
            continue
        pair = text[i:i + 2]

        if ini == "ㅇ":
            if f == "ㅎ":
                cur[2] = ""
                log("PRON.H_DROP", i, f"{pair}: ㅎ 받침 탈락")
            elif f in _CLUSTER_SPLIT:
                a, b = _CLUSTER_SPLIT[f]
                cur[2], nxt[0] = a, b
                log("PRON.LINK", i, f"{pair}: 겹받침 뒤 자음 연음")
            elif f in ("ㄷ", "ㅌ") and nxt[1] == "ㅣ":
                cur[2], nxt[0] = "", {"ㄷ": "ㅈ", "ㅌ": "ㅊ"}[f]
                log("PRON.PALATAL", i, f"{pair}: 구개음화")
            elif f != "ㅇ":
                cur[2], nxt[0] = "", f if f not in _DOUBLE_CODA else f
                log("PRON.LINK", i, f"{pair}: 받침 {f} 연음")
            continue

        # 거센소리되기
        if f == "ㅎ" and ini in _ASPIRATE:
            cur[2], nxt[0] = "", _ASPIRATE[ini]
            log("PRON.ASPIRATE", i, f"{pair}: ㅎ+{ini} → {_ASPIRATE[ini]}")
            continue
        rep = _CODA_REP.get(f, f)
        if ini == "ㅎ" and rep in _ASPIRATE:
            cur[2], nxt[0] = "", _ASPIRATE[rep]
            log("PRON.ASPIRATE", i, f"{pair}: {rep}+ㅎ → {_ASPIRATE[rep]}")
            continue

        # 받침 대표음
        if rep != f:
            if f in _CLUSTER_SPLIT:
                warnings.append(f"{pair}: 겹받침 세부 규칙은 단순화됨")
            cur[2] = rep
            log("PRON.CODA", i, f"{pair}: 받침 {f} → {rep}")
        f = cur[2]

        # 비음화 / 유음화
        if ini == "ㄹ" and f in ("ㅁ", "ㅇ"):
            nxt[0] = "ㄴ"
            log("PRON.NASAL", i, f"{pair}: ㄹ → ㄴ")
        elif ini == "ㄹ" and f in _NASAL:
            nxt[0], cur[2] = "ㄴ", _NASAL[f]
            log("PRON.NASAL", i, f"{pair}: {f}+ㄹ → {_NASAL[f]}+ㄴ")
        elif ini in ("ㄴ", "ㅁ") and f in _NASAL:
            cur[2] = _NASAL[f]
            log("PRON.NASAL", i, f"{pair}: {f} → {_NASAL[f]}")
        elif (f, ini) in (("ㄴ", "ㄹ"), ("ㄹ", "ㄴ")):
            cur[2], nxt[0] = "ㄹ", "ㄹ"
            log("PRON.LIQUID", i, f"{pair}: ㄹㄹ")
        elif f in ("ㄱ", "ㄷ", "ㅂ") and ini in _TENSE:
            nxt[0] = _TENSE[ini]
            log("PRON.TENSE", i, f"{pair}: {ini} → {_TENSE[ini]}")

    # 자음을 첫소리로 가진 음절의 ㅢ → ㅣ (연음 이후 초성 기준)
    for i, s in enumerate(syl):
        if s[1] == "ㅢ" and s[0] != "ㅇ":
            s[1] = "ㅣ"
            log("PRON.UI", i, f"{text[i]}: ㅢ → ㅣ")

    # 마지막 음절 받침 대표음
    last = syl[-1]
    if last[2] and _CODA_REP.get(last[2], last[2]) != last[2]:
        rep = _CODA_REP[last[2]]
        log("PRON.CODA", len(syl) - 1, f"{text[-1]}: 받침 {last[2]} → {rep}")
        last[2] = rep

    return Pronunciation(text, "".join(compose(*s) for s in syl), rules, warnings)
