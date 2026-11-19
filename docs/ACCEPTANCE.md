# 인수 기준 점검 (ACCEPTANCE)

> 기획서 §23(전체 수용 기준) · §32(추가 수용 기준) · §33.4(구독형 전용 완료 기준). 1.0.0rc1, 2026-11-19.
> 상태: **충족**(자동 테스트·실제 서버 확인) / **조건부**(구현 완료, 사용자 확인·외부 자료 필요) / **최종 단계**(브라우저 E2E).

## §23 전체 기능 수용 기준

| # | 기준 | 상태 | 근거 |
|---|---|---|---|
| 1 | 조건 입력 후 한글·한자 후보 생성/저장/복원 | 충족 | `test_project_crud_and_generation_saves_candidates`, `test_backup_roundtrip_reproduces_results` |
| 2 | 한글 이름 → 허용 독음 기준 한자 조합 검색, 미검증 격리 | 충족(공식 자료 적재 시 통과/차단, 미적재 시 '보류') | `test_reverse_search_*`, `test_official_data_moves_combinations_to_passed_or_rejected` |
| 3 | 동일 입력·규칙·데이터 버전에서 사주·수리 결과 일관 | 충족 | 속성 기반 결정론 테스트, golden 60건(사주 23·수리 17·발음 20) |
| 4 | 09:00~12:00 시간 구간을 경계에 따라 분할 | 충족 | `SAJU-RANGE-001~003`, `SAJU-BOUND-IPCHUN` |
| 5 | 한글 전용 이름에 한자 획수 임의 계산 안 함 | 충족 | `NUM-NA-001`, `test_hangul_only_never_computes_strokes` |
| 6 | AI 완전 비활성에서도 생성·분석·비교 | 충족 | `test_ai_disabled_flow_still_works`, 실제 서버(모든 AI 꺼짐) |
| 7 | 이름별 근거·공식·데이터 버전·확인일 추적 | 충족 | 응답 공통 필드, 상세 화면 근거 표, 보고서 버전·확인일 |
| 8 | 부모 공동 평가·토너먼트·결선·출생 확정 후 재평가 | 충족 | `test_phase9.py` |
| 9 | 외부 문서 OCR 오인식 시 사용자 수정·원문 대비 | 조건부 — OCR 미지원(직접 입력), 텍스트/PDF 추출값 수정·원문 보존은 충족 | `test_review_correct_then_crosscheck` |
| 10 | 공식 출생신고 적합성 미확인 시 확정 완료로 표시 안 함 | 충족 | `test_finalize_*` (`never_final`) |
| 11 | 백업 복원 후 비교·보고서 결과 재현 | 충족 | `test_backup_roundtrip_reproduces_results`, 실제 서버 순위 동일 |

## §32 추가 수용 기준

| # | 기준 | 상태 | 근거 |
|---|---|---|---|
| 1 | Ollama 로컬 API 작동·통계 수집 | 충족(가짜 서버 + 실제 phi4-mini 1회). 현재 사용자 설정으로 꺼짐 | `test_ollama_generation_validated_and_recorded` |
| 2 | Claude Code/Antigravity 공식 범위 안에서만 호출·모니터링 | 충족(가짜 CLI). 실제 생성 호출은 하지 않음(기본 꺼짐) | `test_cli_*` |
| 3 | Provider·모델 선택, 미지원 경로는 수동 전달/규칙 기반 | 충족 | `test_model_selection_to_recommendation_flow`, `test_manual_handoff_roundtrip` |
| 4 | 세 Provider 를 한 화면에서 신뢰도·단위·마지막 동기화 확인 | 충족 | `/ai/usage`, `phase11.test.tsx` |
| 5 | 공식 수치 없으면 사용량·잔여 한도를 꾸며내지 않음 | 충족 | `test_usage_summary_never_sums_and_marks_sources` |
| 6 | 인증 토큰·쿠키·프롬프트/코드 원문 수집 안 함 | 충족 | `test_code_does_not_touch_auth_caches`, 사용량 내보내기 검사 |
| 7 | 샘플 데이터는 항상 샘플로 표시 | 충족 | `test_demo_data_is_separated` |
| 8 | 기존 작명 기능·계산 테스트 회귀 없음 | 충족 | 전체 pytest 241 · vitest 26 통과 |

## §33.4 구독형 전용 완료 기준

| 기준 | 상태 |
|---|---|
| `.env.example` 에 유료 API 키 필수 항목 없음 | 충족 (`test_env_example_has_no_paid_api_keys`) |
| 모든 AI 실행에 provider·mode·model·source_type·observed_at·quota_data_status 기록 | 충족 (`ai_invocations`) |
| CLI 미설치·비로그인·권한 없음·자동화 미지원·로그 접근 불가 상태별 처리 | 충족(가짜 CLI: 미설치·꺼짐·한도·오류) — 실제 비로그인 상태 확인은 사용자 환경에서 |
| 구독 계정 전체 사용량과 NameCraft 로컬 활동 혼동 없음 | 충족 (UI·API 라벨 테스트) |
| 토큰·쿠키·세션 파일·프롬프트 원문 수집 없음 | 충족 |
| 구독형 Provider 모두 꺼도 로컬 규칙 기반 작명·분석·저장 동작 | 충족 |

## 최종 단계 남은 항목 (사용자 확인)

| 항목 | 관련 |
|---|---|
| KASI 만세력 기준값 11개 대조 → golden `externally_verified` | Phase 3 게이트 |
| 대법원 인명용 한자표 확보·정규화 CSV 적재 | Phase 2·6·10 판정 |
| 81수리 분류 문헌 대조(선택) | Phase 4 |
| JPL 행성력 이용조건 재확인(상용화 전) | Phase 3 |
| 브라우저 E2E(입력→추천→반응→비교→결선→보고서 인쇄, 모바일 폭) | Phase 8·11 |
| 개발 PC 환경변수 `NODE_TLS_REJECT_UNAUTHORIZED=0` 해제 권장 | 보안(THREAT_MODEL §4) |
