"""사주-이름 오행 관계 해석 (trad, 선택 기능) — SAJU.INTERP.COMPLEMENT.SIMPLE.v0

기획서 §6.2: 억부·조후·통관·격국·용신은 학파별 해석이며, '부족 오행 = 반드시 보충' 규칙은 사용하지 않는다.
따라서 이 모듈은 **한 학파의 단순 보완설**을 '참고 해석'으로만 제공한다.
- 기본 꺼짐(프로젝트 preferences.use_saju = true 일 때만 사용, D-030).
- 명식의 표면 오행 개수에서 가장 적은 오행(들)을 '적은 오행', 가장 많은 오행(들)을 '많은 오행'으로 본다.
- 이름 한자의 자원오행(부수 규칙, 배정 가능한 글자만)이 적은 오행이면 +1, 많은 오행이면 −0.5, 나머지 0.
- 점수 = 50 + 50 × 평균(범위 0~100). 자원오행을 배정할 수 있는 글자가 없으면 N/A.
"""

from __future__ import annotations

PROFILE_ID = "saju.complement.simple.v0"
DISCLAIMER = ("한 학파의 단순 보완설에 따른 참고 해석입니다. 학파마다 판단이 다르며, 부족한 오행을 반드시 "
              "보충해야 한다는 뜻이 아닙니다. 과학적 근거가 없습니다.")


def weak_strong(element_counts: dict[str, int]) -> tuple[list[str], list[str]]:
    lo, hi = min(element_counts.values()), max(element_counts.values())
    weak = sorted(e for e, n in element_counts.items() if n == lo)
    strong = sorted(e for e, n in element_counts.items() if n == hi and hi > lo)
    return weak, strong


def complement_score(element_counts: dict[str, int], name_elements: list[str | None]) -> dict:
    weak, strong = weak_strong(element_counts)
    usable = [e for e in name_elements if e]
    if not usable:
        return {"score": None, "weak": weak, "strong": strong, "reason": "자원오행을 배정할 수 있는 글자 없음",
                "profile_id": PROFILE_ID, "status": "traditional_interpretation"}
    pts = [1.0 if e in weak else (-0.5 if e in strong else 0.0) for e in usable]
    score = round(50 + 50 * sum(pts) / len(pts), 1)
    return {"score": max(0.0, min(100.0, score)), "weak": weak, "strong": strong, "name_elements": usable,
            "profile_id": PROFILE_ID, "status": "traditional_interpretation"}


def sensitivity_label(scores: list[float]) -> str:
    """시나리오 간 점수 폭으로 시간 민감도 표시 (선택한 해석 기준에 한정)."""
    if len(scores) < 2:
        return "single_scenario"
    spread = max(scores) - min(scores)
    return "low" if spread <= 10 else "medium" if spread <= 25 else "high"
