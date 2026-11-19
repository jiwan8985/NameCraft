# Phase 진행 현황 (PHASE_STATUS)

| Phase | 목표 | 상태 | 커밋 | 비고 |
|---|---|---|---|---|
| 0 | 요구사항 확정·레퍼런스 확보 | **완료 보고(승인 대기)** | (이 커밋) | 아래 상세 |
| 1 | Monorepo/기반 환경 | 대기 | | |
| 2 | 성씨·한자·어휘 DB | 대기 | | |
| 3 | 만세력·사주 엔진 | 대기 | | |
| 4 | 전통 성명학 | 대기 | | |
| 5 | 언어·의미 평가 | 대기 | | |
| 6 | 생성/역검색 | 대기 | | |
| 7 | 다중 AI·랭킹 | 대기 | | |
| 8 | 상세 분석/비교 | 대기 | | |
| 9 | 시뮬레이션/공동 선택 | 대기 | | |
| 10 | 자료 교차검증·최종 점검 | 대기 | | |
| 11 | 보고서·PWA·백업·AI 관제 | 대기 | | |
| 12 | 성능·보안·출시 | 대기 | | |

## Phase 0 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 산출물 | 파일 |
|---|---|
| REQUIREMENTS | `docs/REQUIREMENTS.md` (요구사항 ID ~90개, 우선순위·Phase 매핑) |
| 데이터 출처 목록 | `docs/DATA_SOURCES.md`, `datasets/source-manifests/*.yaml` (11개) |
| 계산 프로필 사양 | `docs/ANALYSIS_RULES.md` (기본 프로필 `kr-common-2026` 0.1.0-draft) |
| Golden Tests 초안 | `datasets/golden-tests/saju.yaml`, `numerology.yaml` |
| (§32) capability matrix | `docs/AI_CAPABILITY_MATRIX.md` |
| (§32) 사용량 지표 정의 | `docs/AI_CAPABILITY_MATRIX.md` §4 |
| (§32) 모의 사용량 샘플 | `datasets/fixtures/ai-usage-demo.json` (모든 레코드 `is_demo: true`) |
| 기타 | `docs/QA_TEST_PLAN.md`, `docs/DECISIONS.md`, `docs/PROJECT_PLAN.md`, `README.md` |

### 완료 게이트: "출처·라이선스·규칙 정의 검토"
- 규칙 정의: **초안 완료** (검토 필요)
- 출처 목록: **완료**, 라이선스: **미확인** — 모든 출처 `candidate/license_review`. 공식 원문 확인은 사람 검토 항목으로 남김(자동 수집 미실시).
- Capability matrix: 로컬 CLI `--help` 기준 판정 완료. 약관 최종 확인은 사용자 항목.

### Golden Test 현황
| 파일 | definitional | formula_derived | externally_verified | pending |
|---|---:|---:|---:|---:|
| saju.yaml | 0 | 6 | 0 | 4 |
| numerology.yaml | 13 | 0 | 0 | 1 |

(테스트 실행기는 Phase 1에서 구현 — 현재 실행된 테스트 없음)

### 알려진 문제 / 미결
- `docs/DECISIONS.md` Open Questions 1~6.
- formula_derived 사주 기대값은 KASI 등 외부 기준 대조 전이므로 Phase 3 완료 근거가 될 수 없음.

### 다음 Phase(1) 준비 사항
- 개발 도구 결정(Open Questions 1~3) 후 Monorepo 뼈대, FastAPI `/api/v1/health`, Next.js 기본 라우트(§15 전체 라우트 placeholder 포함 AI 라우트), DB(SQLite+Alembic), Provider/Collector 인터페이스 mock, `make test`.
