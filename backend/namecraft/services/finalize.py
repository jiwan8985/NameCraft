"""출생신고 준비 모드 (기획서 §14, REQ-FIN-002).

- 표기 일치(한글·한자 글자 수, 한자 독음 ↔ 한글 음절), 인명용 한자 공식 판정, 데이터 기준일을 점검한다.
- 서비스는 출생신고를 대신하거나 수리를 보장하지 않는다. 공식 자료가 없거나 오래되면 '최종 공식 재확인 필요'.
- 공식 판정이 모두 확인되어도 '확정 완료'로 표시하지 않고 '공식 자료 기준 확인됨 — 최종 재확인 권장'으로 둔다(§23).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from namecraft.db.models import HanjaReading, OfficialNameCharacterRule
from namecraft.domain.text import codepoint, is_compat_hanja, is_hangul_syllable, is_hanja, normalize_name_text
from namecraft.services.lexicon import OFFICIAL_NOT_LISTED, OFFICIAL_VERIFIED, official_data_loaded, official_status

STALE_AFTER = timedelta(days=365)
OFFICIAL_LINKS = [
    {"label": "대법원 전자가족관계등록시스템 — 인명용 한자 조회",
     "url": "https://efamily.scourt.go.kr/cs/CsBltnWrtList.do?bltnbordId=0000010"},
    {"label": "국가법령정보센터 — 가족관계의 등록 등에 관한 규칙", "url": "https://www.law.go.kr/"},
]
DISCLAIMER = ("이 점검은 개인용 참고 자료입니다. NameCraft AI 는 출생신고를 대신하거나 신고의 수리를 보장하지 않습니다. "
              "최종 판단은 가족관계등록 관서와 공식 조회 결과를 따르세요.")


def check(session: Session, *, surname_hangul: str, surname_hanja: str | None, given_hangul: str,
          given_hanja: str | None) -> dict[str, Any]:
    sh = normalize_name_text(surname_hangul)
    sx = normalize_name_text(surname_hanja) if surname_hanja else None
    gh = normalize_name_text(given_hangul)
    gx = normalize_name_text(given_hanja) if given_hanja else None
    checks: list[dict] = []

    def add(cid: str, status: str, message: str, **extra):
        checks.append({"id": cid, "status": status, "message": message, **extra})  # status: pass | warn | fail | recheck

    ok_hangul = bool(gh) and all(is_hangul_syllable(c) for c in sh + gh)
    add("hangul_form", "pass" if ok_hangul else "fail",
        "한글 이름 표기가 완성형 한글입니다." if ok_hangul else "한글 이름에 완성형 한글이 아닌 문자가 있습니다.")
    add("given_length", "recheck" if len(gh) > 5 else "pass",
        "이름(성 제외) 글자 수는 일반적으로 5자 이내로 안내됩니다 — 현행 기준을 공식 확인하세요." if len(gh) > 5
        else f"이름 {len(gh)}자 — 글자 수 기준(통상 5자 이내) 범위", basis="가족관계등록 관련 예규(현행 여부 공식 재확인)")

    chars: list[dict] = []
    if gx is None:
        add("hanja_none", "pass", "한글 이름 — 인명용 한자 판정 대상이 아닙니다.")
    else:
        if len(gx) != len(gh) or not all(is_hanja(c) for c in gx):
            add("hanja_count", "fail", "이름 한자와 한글의 글자 수가 같아야 합니다.")
        else:
            add("hanja_count", "pass", "이름 한자와 한글의 글자 수가 같습니다.")
            for i, ch in enumerate(gx):
                cp = codepoint(ch)
                readings = set(session.scalars(select(HanjaReading.reading).where(HanjaReading.codepoint == cp)))
                off = official_status(session, cp, gh[i])
                reading_ok = gh[i] in readings or gh[i] in off["allowed_readings"]
                chars.append({"position": i, "hanja": ch, "codepoint": cp, "hangul": gh[i],
                              "reading_match": reading_ok, "official": off["status"],
                              "allowed_readings": off["allowed_readings"], "compatibility_char": is_compat_hanja(ch)})
                if not reading_ok:
                    add(f"reading_{i}", "fail", f"'{ch}'의 독음 자료에 '{gh[i]}'가 없습니다. 독음과 한글 표기를 확인하세요.")
                if off["status"] == OFFICIAL_NOT_LISTED:
                    add(f"official_{i}", "fail", f"'{ch}'({gh[i]})는 적재된 공식 인명용 한자표에서 찾을 수 없습니다.")
                elif off["status"] != OFFICIAL_VERIFIED:
                    add(f"official_{i}", "recheck", f"'{ch}'({gh[i]})의 인명용 한자 허용 여부를 공식 조회로 확인해야 합니다.")
                if is_compat_hanja(ch):
                    add(f"compat_{i}", "warn", f"'{ch}'는 호환 한자 코드입니다. 신고 서식·전산 입력 시 같은 글자로 입력되는지 확인하세요.")
    if sx and len(sx) != len(sh):
        add("surname_hanja", "fail", "성씨 한자와 한글의 글자 수가 다릅니다.")
    elif sx:
        add("surname_hanja", "warn", "성씨 한자는 가족관계등록부에 기록된 본래 표기와 같은지 확인하세요.")

    # 데이터 기준일
    loaded = official_data_loaded(session)
    basis: dict[str, Any] = {"official_data_loaded": loaded}
    if loaded:
        latest = session.scalar(select(func.max(OfficialNameCharacterRule.checked_at))
                                .where(OfficialNameCharacterRule.is_sample.is_(False)))
        eff = session.scalar(select(func.max(OfficialNameCharacterRule.effective_date))
                             .where(OfficialNameCharacterRule.is_sample.is_(False)))
        basis.update({"checked_at": latest.isoformat() if latest else None, "effective_date": eff})
        if latest and datetime.now(UTC) - latest.replace(tzinfo=latest.tzinfo or UTC) > STALE_AFTER:
            add("data_stale", "recheck", "공식 한자 자료 확인일이 1년 이상 지났습니다. 최신 고시를 확인하세요.")
    else:
        add("official_data", "recheck", "공식 인명용 한자표가 적재되지 않았습니다. 대법원 조회로 직접 확인하세요.")

    statuses = {c["status"] for c in checks}
    overall = "fix_required" if "fail" in statuses else (
        "official_recheck_required" if "recheck" in statuses else "verified_against_loaded_data")
    return {
        "name": {"surname_hangul": sh, "surname_hanja": sx, "given_hangul": gh, "given_hanja": gx,
                 "full": sh + gh, "full_hanja": (sx or "") + (gx or "") if gx else None},
        "overall": overall,
        "overall_label": {"fix_required": "수정 필요", "official_recheck_required": "최종 공식 재확인 필요",
                          "verified_against_loaded_data": "공식 자료 기준 확인됨 — 신고 전 최종 재확인 권장"}[overall],
        "checks": checks, "characters": chars, "data_basis": basis,
        "checklist": [
            "대법원 인명용 한자 조회에서 이름 한자를 한 글자씩 검색해 허용 여부·독음을 확인",
            "신고서의 한글 이름과 한자 이름이 같은 글자 수·같은 순서인지 확인",
            "성씨 한자가 부모의 가족관계등록부 표기와 같은지 확인",
            "출생신고 기한·제출 서류는 관할 관서 안내를 따름",
        ],
        "official_links": OFFICIAL_LINKS,
        "disclaimer": DISCLAIMER,
        "never_final": True,
    }
