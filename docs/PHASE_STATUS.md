# Phase 진행 현황 (PHASE_STATUS)

| Phase | 목표 | 상태 | 커밋 | 비고 |
|---|---|---|---|---|
| 0 | 요구사항 확정·레퍼런스 확보 | 완료(승인됨) | b224e69 | |
| 1 | Monorepo/기반 환경 | 완료(승인됨) | 3a72eea | |
| 2 | 성씨·한자·어휘 DB | **완료 보고(승인 대기) — 공식 데이터 항목 부분 완료** | (이 커밋) | 아래 상세 |
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

## Phase 2 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| DB schema | 마이그레이션 `0002` — hanja_characters / readings / variants / stroke_counts / element_mappings, official_name_character_rules, surnames / surname_variants, dictionary_terms, name_popularity_datasets / rows (11 테이블) |
| seed | Unihan 18.0.0 → 한자 8,525자 · 독음 8,917 · 현대 필획 8,525 · 이체자 5,930 (모두 `unverified`). 성씨 시드 120개(단성 112 + 복성 8) |
| import pipeline | `tasks.py fetch-unihan / import-data / import-official` — 체크섬·data_release_versions 기록, 재실행 멱등, 출처 manifest → reference_sources 동기화 |
| 조회 API | `GET /surnames`, `POST /surnames/provisional`, `GET /hanja`, `GET /hanja/{cp}`, `GET /admin/data` |
| UI | `/admin/data` — 데이터 현황·출처·데이터 버전, 공식 자료 미적재 경고 |
| 텍스트 정규화 | 호환 한자 보존(NFC 접기 금지), 한글 자모 합성 (D-013) |

### 완료 게이트: "이체자·독음·획수 출처 검증"
| 항목 | 결과 |
|---|---|
| 이체자 | 호환한자 ↔ 통합한자 링크(예: U+F9E1 李(이) → U+674E), 조회 시 계열 함께 반환, NFC로 접히지 않음 — **통과** |
| 독음 | 다중 독음(樂: 낙·락·악·요)과 플래그별 인명용 힌트 분리, 출처 `SRC-UNIHAN`·상태 `unverified` 필수 — **통과** |
| 획수 | 현대 필획만 적재(`STROKE.MODERN.UNIHAN.v1`), 원획 0건(Phase 4) — 필드·규칙 분리 **통과** |
| 성씨 교차검증 | 시드 120개 한자 독음을 Unihan과 자동 대조 → 충돌 0 |
| 공식 판정 분리 | 공식 미적재 시 `unknown` + 경고, 샘플은 `sample_only`, 실제 적재 시 `verified` / `not_listed` / 출처 충돌 시 `conflict` — 테스트로 검증 |
| **공식 인명용 한자표 적재** | **미완료** — 원본 파일·이용조건 미확보. 가져오기 경로(정규화 CSV)만 구현·테스트 |
| 어휘(dictionary_terms) | 스키마만. 국립국어원 자료 이용조건 확인 후 Phase 5에서 적재 |
| 이름 통계 | 스키마만. 공개 통계 수동 확인 후 적재 |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 2 신규: 정규화 5, 가져오기 12, 조회 API 10) | 48 | 0 |
| vitest (신규: 데이터 관리 화면 1) | 10 | 0 |
| tsc / next build | 통과 | |
| 실제 기동: 전체 Unihan 적재 후 프록시 경유 조회(심 인명 한자 15자, 沈 계열 U+6C88·U+F972) | 정상 | |
| Docker compose: 컨테이너 기동 시 import-data → 조회 | 정상 | |

### 알려진 문제 / 메모
- 성씨 시드·Unihan 독음은 공식 근거가 아님 — 화면·API 모두 `unverified`로 표시.
- Unihan `kKoreanName`은 2015/2018판 기준이라 현행 인명용 한자표와 다를 수 있음.
- 개발 서버 종료: 세션 도구의 강제 종료로는 Windows 측 자식 프로세스에 신호가 전달되지 않아 수동 정리함. 터미널 Ctrl+C 경로의 트리 종료는 아직 직접 확인하지 못함.

### 다음 Phase(3) 준비 사항
- 만세력·사주 엔진: 음양력 변환, 절기(천문 계산), 사주 4주, 자시 옵션, 시간 범위 분할. **외부 기준값(KASI) 대조가 완료 게이트** — 조회 방법(웹 수동 조회 또는 사용자가 발급한 공공데이터 API 키) 결정 필요.

## Phase 1 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| Next.js | `apps/web` — Next 16.4 + React 19.3 + Tailwind v4 + shadcn/ui 방식 컴포넌트, §15 화면 19개 라우트(placeholder), 반응형 내비, PWA manifest, 라이트/다크 토큰 |
| FastAPI | `apps/api/namecraft_api` — 앱 팩토리, 공통 응답 envelope(REQ-NF-001), 구조화 오류, CORS 제한 |
| DB | SQLAlchemy 2 + Alembic, SQLite 기본. 마이그레이션 `0001`(users, audit_logs, reference_sources, data_release_versions) |
| Docker | `docker-compose.yml` + `docker/*.Dockerfile`, 127.0.0.1 바인딩 |
| CI 없는 로컬 테스트 명령 | `python scripts/tasks.py test` (pytest + vitest + tsc) |
| 기본 인증 | 로컬 단일 사용자 토큰 + Next 서버 프록시(토큰 브라우저 비노출, 교차 출처/CSRF 차단) |
| (§32) AI UI 라우트·Collector 뼈대 | `AIProvider`/`UsageCollector` 프로토콜, mock 3종, `/api/v1/ai/providers` (mock 표시), `/ai/providers` 화면 + 오류 UX(규칙 기반 폴백 안내·재시도) |
| 기타 | PII 로그 마스킹 필터, `.env.example`(유료 API 키 없음), `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` |

### 완료 게이트: "원클릭 로컬 기동 · API 헬스체크"
| 확인 | 결과 |
|---|---|
| `tasks.py dev` 실제 기동 → `GET /api/v1/health` | 200, `db: {ok: true, revision: "0001"}` |
| 토큰 없이 보호 API | 401 |
| 웹 프록시 경유 `/ai/providers` | 200, mock 3종 (ollama unknown / claude_code·antigravity disabled) |
| 프록시 교차 출처 요청 / CSRF 헤더 없는 POST | 403 / 403 |
| 웹 라우트 `/dashboard`, `/ai/providers`, `/projects/abc/recommendations`, `/admin/data` | 200 |
| `docker compose build` + `up` → health·프록시 | 성공 (동일 결과) |
| `next build` (프로덕션) | 성공, 경고 0 |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest (API 기반 6, AI mock 6, 보안 정책 5, 데이터셋 구조 4) | 21 | 0 |
| vitest (라우트 IA 2, 프록시 가드 4, Provider UI·배지 3) | 9 | 0 |
| tsc --noEmit | 통과 | |

Golden test의 **계산** 검증은 아직 없음(구조 검증만) — Phase 3·4 범위.

### 알려진 문제 / 메모
- 런타임은 Windows Python 3.14 + Windows Node 24(D-010). WSL에서 `uv` 설치가 자동 권한 정책으로 거부되어 기존 설치 도구를 사용함.
- Windows에서 `tasks.py dev` 종료 시 uvicorn reload 워커가 남는 문제 발견 → `taskkill /T`로 트리 종료하도록 수정(수정 후 재기동 검증은 미실시, 테스트 스위트는 재통과).
- `packages/contracts`·`packages/design-system`은 필요 시점까지 보류(ARCHITECTURE.md §2).

### 다음 Phase(2) 준비 사항
- 성씨·한자·어휘 DB 스키마/시드/import 파이프라인/조회 API. **공식 인명용 한자표 파일과 이용조건 확인이 필요**(DATA_SOURCES §4) — 확보 전에는 Unihan 기반 `unverified` 데이터와 소규모 sample로 파이프라인만 검증.

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
