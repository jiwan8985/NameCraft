# QA 테스트 계획 (QA_TEST_PLAN)

> 기획서 §22, §32, §33.4 기준. Phase 0 초안 — 각 Phase 시작 시 해당 절을 구체화한다.

## 1. 테스트 계층과 도구

| 계층 | 범위 | 도구(예정) | 실행 명령(예정) |
|---|---|---|---|
| 단위 | 도메인 계산(달력·사주·수리·발음), 정규화, 가중치 | pytest, hypothesis | `make test-api` |
| Golden | `datasets/golden-tests/*.yaml` 로더 기반 파라미터 테스트 | pytest | `make test-golden` |
| 속성 기반 | 결정론, 중복 없음, 제약 준수, 가중치 정규화 | hypothesis | 단위에 포함 |
| 계약 | OpenAPI 스키마·공통 응답 필드(REQ-NF-001) | schemathesis 또는 pytest | `make test-contract` |
| 프런트 단위 | 컴포넌트·상태 배지 | vitest + testing-library | `make test-web` |
| E2E | 생성→분석→비교→시뮬레이션→보고서, 모바일 | Playwright | `make test-e2e` |
| 보안 | 권한 우회, 업로드, LLM 출력 주입, 로그 누출, 인증정보 미수집 | pytest + 정적 grep 검사 | `make test-security` |

CI 서비스는 사용하지 않고(기획서 Phase 1 "CI 없는 로컬 테스트 명령"), `make test` 한 번으로 전체 로컬 실행.

## 2. Golden Test 정책

- `status: definitional` — 공식 정의 자체 검증. 실패 = 버그.
- `status: formula_derived` — 공식으로 산출했으나 외부 기준 미대조. 통과해도 Phase 3 완료 조건 불충족.
- `status: externally_verified` — 출처·조회일 기록. Phase 3/4 완료 게이트는 이 상태 케이스로 판단.
- `status: pending` — `xfail/skip`. **통과로 집계하지 않음**(기획서 §21.1).

## 3. 필수 경계 테스트 (기획서 §22.2) → 담당 Phase

| 경계 사례 | Phase | 테스트 ID(예정) |
|---|---|---|
| 복성 | 2, 4 | NUM-4GYEOK-002, SN-COMPOUND-* |
| 동음이한자 성씨 | 2 | SN-HOMOPHONE-* |
| 외자 | 4 | NUM-4GYEOK-003/004 |
| 한글 전용 이름 | 4, 5 | NUM-NA-001 |
| 3음절 이상 이름 | 4 | NUM-4GYEOK-005 |
| 여러 독음 한자 | 2, 6 | HJ-MULTIREAD-* |
| 호환한자(U+F900–FAFF) | 2 | HJ-COMPAT-* |
| 윤달 | 3 | SAJU-BOUND-LEAP |
| 절기 직전/직후 | 3 | SAJU-BOUND-IPCHUN |
| 자정/자시 | 3 | SAJU-BOUND-ZI |
| 타임존·역사적 표준시 | 3 | SAJU-BOUND-KST-HIST |
| 시간 미정 | 3 | SAJU-BOUND-UNKNOWN-TIME |
| 모델 미설치 | 7 | AI-OLLAMA-MISSING |
| 공식 데이터 충돌 | 2 | HJ-CONFLICT-* |
| 인기도 없는 이름 | 8 | POP-NODATA-* |
| 보고서 재생성 | 11 | RPT-REPRO-* |

## 4. AI Provider / 사용량 QA (기획서 §32, §33.4)

| 테스트 | 기대 |
|---|---|
| CLI 미설치 | `unavailable` + 규칙 기반 폴백 |
| 비로그인 | `unavailable(auth_required)`, 로그인 안내만, 자동 로그인 시도 없음 |
| 권한 없음/공식 자동화 미지원 | `manual_handoff`/`monitor_only` |
| 로그 접근 불가 | 사용량 `unknown`, 숫자 미생성 |
| 서브프로세스 환경 | `*_API_KEY` 변수 제거 확인 |
| `--bare`/권한 우회 플래그 | 명령 구성에 포함되지 않음(정적 테스트) |
| 인증 파일 미접근 | 수집기가 허용목록 경로만 열람(파일 접근 목 테스트) |
| 데모 데이터 혼입 | `is_demo` 레코드가 실제 집계·알림에 포함되면 실패 |
| 단위 불일치 | 서로 다른 `metric_unit` 합산 시도 시 오류 |
| 계정 전체 vs NameCraft 내부 | UI 라벨이 구분되는지 E2E |
| 한도 초기화 경계/DST | `reset_at` 경과 후 상태 `stale` 전환 |
| 새 Provider 전송 전 동의 | 동의 없으면 전송 0건 |
| 모든 구독형 비활성 | 규칙 기반 생성·분석·저장 정상 |

## 5. 금지 표현 lint (REQ-NF-005)

해설 템플릿·AI 출력 검증에 금지 패턴(예: "반드시 성공", "건강을 보장", "운명이 결정") 탐지 → 경고/차단. 목록은 Phase 5에서 확정.

## 6. Phase 완료 보고 형식

각 Phase 종료 시 `docs/PHASE_STATUS.md`에 기록: 통과/미통과 테스트 수, `pending` 수, 변경 파일 요약, 알려진 문제, 다음 Phase 준비 사항.
