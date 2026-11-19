"""천간·지지·60갑자 정의와 결정론적 규칙 (ANALYSIS_RULES.md §2)."""

from __future__ import annotations

from dataclasses import dataclass

STEMS = "甲乙丙丁戊己庚辛壬癸"
STEMS_KO = "갑을병정무기경신임계"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
BRANCHES_KO = "자축인묘진사오미신유술해"
STEM_ELEMENT = "木木火火土土金金水水"
BRANCH_ELEMENT = "水土木木土火火土金金土水"
ELEMENTS = "木火土金水"


@dataclass(frozen=True)
class Pillar:
    index: int  # 0..59, 甲子=0

    @classmethod
    def of(cls, stem: int, branch: int) -> "Pillar":
        # stem ≡ i (mod 10), branch ≡ i (mod 12) 를 만족하는 유일한 i (같은 홀짝일 때만 존재)
        if (stem - branch) % 2:
            raise ValueError("stem/branch parity mismatch")
        return cls(next(i for i in range(60) if i % 10 == stem % 10 and i % 12 == branch % 12))

    @property
    def stem(self) -> int:
        return self.index % 10

    @property
    def branch(self) -> int:
        return self.index % 12

    @property
    def hanja(self) -> str:
        return STEMS[self.stem] + BRANCHES[self.branch]

    @property
    def hangul(self) -> str:
        return STEMS_KO[self.stem] + BRANCHES_KO[self.branch]

    def to_dict(self) -> dict:
        return {
            "index": self.index, "hanja": self.hanja, "hangul": self.hangul,
            "stem": STEMS[self.stem], "branch": BRANCHES[self.branch],
            "stem_element": STEM_ELEMENT[self.stem], "branch_element": BRANCH_ELEMENT[self.branch],
            "stem_yinyang": "양" if self.stem % 2 == 0 else "음",
            "branch_yinyang": "양" if self.branch % 2 == 0 else "음",
        }


def year_pillar(saju_year: int) -> Pillar:
    """SAJU.YEAR.v1 — 입춘 기준 연도."""
    return Pillar((saju_year - 4) % 60)


def month_pillar(year_stem: int, month_no: int) -> Pillar:
    """SAJU.MONTH.v1 — month_no 0=寅월 … 11=丑월. 오호둔: 甲己→丙寅, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅."""
    first_stem = ((year_stem % 5) * 2 + 2) % 10
    return Pillar.of((first_stem + month_no) % 10, (2 + month_no) % 12)


def day_pillar_from_jdn(jdn: int) -> Pillar:
    """SAJU.DAY.v1 — 일진 idx = (JDN + 49) mod 60."""
    return Pillar((jdn + 49) % 60)


def hour_pillar(day_stem: int, hour_branch: int) -> Pillar:
    """SAJU.HOUR.v1 — 오서둔: 甲己일→甲子, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子."""
    zi_stem = ((day_stem % 5) * 2) % 10
    return Pillar.of((zi_stem + hour_branch) % 10, hour_branch)


def hour_branch_from_hours(hours: float) -> int:
    """子: 23–01, 丑: 01–03, … (hours: 0 ≤ h < 24)."""
    return int(((hours + 1) % 24) // 2)


def element_counts(pillars: list[Pillar]) -> dict[str, int]:
    """SAJU.ELEMENTS.v1 — 천간·지지 표면 오행 개수(지장간 미포함)."""
    counts = dict.fromkeys(ELEMENTS, 0)
    for p in pillars:
        counts[STEM_ELEMENT[p.stem]] += 1
        counts[BRANCH_ELEMENT[p.branch]] += 1
    return counts
