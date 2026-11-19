"""테스트용 Unihan 부분집합 생성 (datasets/fixtures/unihan-subset.zip).

사용: python scripts/build_unihan_fixture.py <원본 Unihan.zip> <license.txt>
대상: 성씨 시드 한자 + 경계 사례·golden test 글자 + 호환 한자.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXTRA_CHARS = "樂學龍丁沈金李秀晶智敏俊瑞恩河娥雅珉四郞一二三五十浩花蓮道陳玉理珍心志性情慧"
COMPAT = {"U+F9E1", "U+F914", "U+F95C", "U+F9BF", "U+F9C4", "U+F972", "U+F90A"}


def main(src_zip: str, license_txt: str) -> None:
    seed = yaml.safe_load((ROOT / "datasets/seed/surnames.yaml").read_text(encoding="utf-8"))
    chars = set(EXTRA_CHARS)
    for s in seed["surnames"]:
        chars |= set(s["hanja"])
    cps = {f"U+{ord(c):04X}" for c in chars} | COMPAT
    src = zipfile.ZipFile(src_zip)
    with zipfile.ZipFile(ROOT / "datasets/fixtures/unihan-subset.zip", "w", zipfile.ZIP_DEFLATED) as out:
        for name in src.namelist():
            lines = []
            for line in io.TextIOWrapper(src.open(name), encoding="utf-8"):
                if line.startswith("#"):
                    if len(lines) < 12:
                        lines.append(line)
                    continue
                if line.split("\t", 1)[0] in cps:
                    lines.append(line)
            out.writestr(name, "".join(lines))
        out.writestr("LICENSE-Unicode.txt", Path(license_txt).read_text(encoding="utf-8"))
    print(len(cps), "codepoints")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
