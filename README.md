# NameCraft AI

출생 예정 아동의 작명부터 기존 이름 분석·비교·최종 선정까지 지원하는 **검증 가능한** 개인용·로컬 우선 작명 플랫폼.

- SSOT 기획서: [`NameCraft_AI_MASTER_PLAN_v2.1.md`](NameCraft_AI_MASTER_PLAN_v2.1.md)
- 진행 현황: [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md)

## 원칙 요약
- 법적 사실 · 결정론적 계산 · 전통 해석 · 주관/AI 평가를 분리 표시합니다.
- AI는 후보 제안과 설명에만 사용하며, 한자 허용·획수·사주 계산을 대신하지 않습니다.
- AI(Ollama / Claude Code / Antigravity)는 선택 기능입니다. 유료 API 키 입력·종량제 연결은 제공하지 않습니다.
- 이름 해석은 문화적 참고 자료이며 건강·성공·운명을 보증하지 않습니다.

## 현재 상태
Phase 0(요구사항·데이터 출처·계산 규칙·Golden Test 초안) 완료. 실행 가능한 코드는 Phase 1부터 추가됩니다.

## 디렉터리
```
docs/                      요구사항·규칙·출처·QA·결정·진행 현황
datasets/source-manifests/ 데이터 출처·라이선스 manifest
datasets/golden-tests/     계산 기준 테스트 케이스(상태 포함)
datasets/fixtures/         DEMO 데이터(운영 사용 금지)
```
