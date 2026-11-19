# API 계약 (API_CONTRACT)

> 기획서 §18 기준. 기계 판독 스키마: 실행 중 `GET /api/v1/openapi.json`.

## 공통 응답

```json
{
  "status": "ok | degraded | error",
  "data": {},
  "data_version": "unreleased",
  "rule_profile": null,
  "rule_version": null,
  "calculation_assumptions": [],
  "verification_status": "verified | calculated | traditional_interpretation | subjective | unverified | not_applicable | conflict | mock | null",
  "warnings": [{ "code": "...", "message": "..." }],
  "provenance": [],
  "generated_at": "ISO-8601 UTC"
}
```

## 오류 응답

```json
{ "status": "error", "error": { "code": "unauthorized | not_found | validation_error | provider_unavailable | ...", "message": "...", "details": {} } }
```

## 구현 현황

| Method | Endpoint | 인증 | Phase | 상태 |
|---|---|---|---|---|
| GET | `/api/v1/health` | 불필요 | 1 | 구현 — DB 연결·마이그레이션 리비전 포함, 미적용 시 `db_not_migrated` 경고 |
| GET | `/api/v1/auth/whoami` | 필요 | 1 | 구현 — `local_single_user` |
| GET | `/api/v1/ai/providers` | 필요 | 7 | 구현 — 실제 탐지(연결 상태·실행 모드·모델·기능). 구독형은 기본 `disabled` |
| POST | `/api/v1/ai/providers/{provider}/test` | 필요 | 7 | 구현 — 읽기 전용 상태 확인(`status_only`), 생성·한도 소모 없음 |
| PATCH | `/api/v1/ai/preferences` | 필요 | 7 | 구현 — 활성화·실행 명령·모델·시간 제한·자동 대체 순서/허용. 금지 플래그 거부 |
| POST | `/api/v1/ai/generate` | 필요 | 7 | 구현 — `provider: auto/ollama/claude_code/antigravity/none`, `dry_run`(전송 미리보기), 외부 Provider 는 `consent: true` 필수. 실패 시 규칙 기반 폴백 |
| POST | `/api/v1/ai/handoff/prompt`, `/ai/handoff/import` | 필요 | 7 | 구현 — 수동 전달용 프롬프트 / 붙여넣은 JSON 검증 |
| GET | `/api/v1/surnames?q=` | 필요 | 2 | 구현 — 한글·한자·두음 변형(리/류 등) 검색, 동음이한자 전부 반환, 글자별 현대 필획(unverified)·원획(not_available) |
| POST | `/api/v1/surnames/provisional` | 필요 | 2 | 구현 — 사전 외 성씨 임시 레코드(`is_provisional`, `SRC-USER-INPUT`, 확정 보류) |
| GET | `/api/v1/hanja?char=&reading=&name_only=&limit=` | 필요 | 2 | 구현 — 독음 역검색, 글자 조회 시 호환한자 계열 함께 반환 |
| GET | `/api/v1/hanja/{codepoint}` | 필요 | 2 | 구현 — 상세(독음·획수·이체자·비공식 힌트·공식 판정) |
| GET | `/api/v1/admin/data` | 필요 | 2 | 구현 — 데이터 현황·출처·데이터 버전(체크섬) |
| POST | `/api/v1/saju/calculate` | 필요 | 3 | 구현 — 양력/음력(윤달), 정확 시각·시간 범위·시간 미정, 진태양시·자시 옵션, 구간별 4주·오행 개수·변경 기둥·인근 절입 시각. 입력 저장·로그 없음 |
| GET | `/api/v1/calendar/solar-terms?year=` | 필요 | 3 | 구현 — 해당 연도 24절기 절입 시각(UTC·지역시) — KASI 대조용 |
| POST | `/api/v1/numerology/calculate` | 필요 | 4 | 구현 — 원형이정 4격(calc)·수리오행·음양 배열 / 81수리·음양 판단·삼원·자원오행(trad, 출처 대조 전) / 음령오행 두 학파 + 일치도. 한글 전용 이름은 획수 항목 `not_applicable`, 획수 모르는 한자는 `unknown` |
| POST | `/api/v1/names/analyze` | 필요 | 5 | 구현 — 발음(추정·루브릭)·부정 연상 후보·한자 뜻 주의·연령별 참고·로마자 + 수리 분석. 섹션마다 `status`(calculated/subjective/candidate/not_available) |
| POST | `/api/v1/names/similarity` | 필요 | 5 | 구현 — 후보 쌍별 유사도·중복 (최대 50개) |
| POST | `/api/v1/names/generate` | 필요 | 6 | 구현 — 규칙 기반 생성. 결과 `passed`(공식 확인 또는 한글 이름) / `on_hold`(공식 미확인) / `quarantined`(비속어·비하 정확 일치), 통계(하드 필터 제거 수·다양성 건너뜀 등) |
| POST | `/api/v1/names/reverse-search` | 필요 | 6 | 구현 — 한글 이름 → 음절별 인명용 독음 한자 → 조합별 정렬 점수(구성요소·가중치 공개), `passed/on_hold/rejected` |
| POST | `/api/v1/names/alternative-hanja` | 필요 | 6 | 구현 — 현재 한자 조합에서 글자별 우려 사항과 점수가 개선되는 대안 |
| POST/GET/PATCH | `/api/v1/projects`, `/projects/{id}` | 필요 | 7 | 구현 — 프로젝트(성씨·성별 선호·선호·하드 조건·분석 옵션) |
| POST | `/api/v1/projects/{id}/candidates/generate` | 필요 | 7 | 구현 — 규칙/AI 생성 후 저장(기존 후보·제외 이름 재생성 안 함) |
| POST/GET | `/api/v1/projects/{id}/candidates?sort=` | 필요 | 7 | 구현 — 수동 추가 / 종합·항목별 랭킹(`overall, phonetic, meaning, saju, numerology, usability, preference`) |
| PATCH | `/api/v1/candidates/{id}` | 필요 | 7 | 구현 — `active/excluded/favorite` (제외 해제 = 다시 추천 허용) |
| POST | `/api/v1/reactions` | 필요 | 7 | 구현 — 좋아요/싫어요/보류·이유·메모. 싫어요 → 제외 |
| GET | `/api/v1/candidates/{id}` | 필요 | 8 | 구현 — 이름 상세: 전체 분석 + 항목별 점수 근거 + 반응 이력 + 생성 기록(모델·프롬프트·seed) + 템플릿 요약 |
| POST | `/api/v1/names/compare` | 필요 | 8 | 구현 — 2~10개 이름을 같은 가중치·프로필로 비교 + 쌍별 유사도 |
| 기타 §18 엔드포인트 | | 필요 | 9~11 | 미구현 |

### `POST /saju/calculate` 요청

```json
{ "calendar": "solar | lunar", "date": "2027-01-15", "is_leap_month": false,
  "time": "10:00" | null, "time_range": ["09:00", "12:00"] | null, "tz": "Asia/Seoul",
  "longitude": 126.978 | null,
  "options": { "true_solar_time": "off | longitude_only | with_equation_of_time",
               "zi_convention": "jojasi_next_day | yajasi_same_day" } }
```
`time`·`time_range` 둘 다 없으면 시간 미정(하루 전체 분할). 오류 코드: `calendar_input_invalid`, `out_of_supported_range`, `ephemeris_unavailable`.

### 한자 응답의 `official.status`

| 값 | 의미 | 표시 |
|---|---|---|
| `verified` | 공식 인명용 한자표(비샘플)에 수록 | 공식 확인 |
| `not_listed` | 공식 자료는 적재되어 있으나 미수록 | 인명 사용 불가 가능성 — 공식 재확인 권장 |
| `unknown` | 공식 자료 미적재 | 판정 불가 (`official_data_missing` 경고) |
| `sample_only` | 샘플 CSV에만 존재 | 판정 근거 아님 |

`readings[].is_name_reading` 과 `hints.unihan_korean_name` 은 **Unihan 기반 비공식 힌트**이며 `official` 과 별개다.

## 웹 프록시

브라우저는 `/api/proxy/<path>` → `/api/v1/<path>`로 호출한다. 변경 메서드는 `x-namecraft-request: 1` 헤더 필수. 프록시 자체 오류 코드: `cross_site_request`, `csrf_header_missing`, `invalid_path`, `api_token_missing`(503), `api_unreachable`(502).
