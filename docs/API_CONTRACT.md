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
| GET | `/api/v1/ai/providers` | 필요 | 1 → 7 | **mock** (`verification_status: mock`, 각 항목 `is_mock: true`) |
| POST | `/api/v1/ai/providers/{provider}/test` | 필요 | 1 → 7 | **mock** (`test_result: skipped_mock`), 미지원 provider는 404 |
| GET | `/api/v1/surnames?q=` | 필요 | 2 | 구현 — 한글·한자·두음 변형(리/류 등) 검색, 동음이한자 전부 반환, 글자별 현대 필획(unverified)·원획(not_available) |
| POST | `/api/v1/surnames/provisional` | 필요 | 2 | 구현 — 사전 외 성씨 임시 레코드(`is_provisional`, `SRC-USER-INPUT`, 확정 보류) |
| GET | `/api/v1/hanja?char=&reading=&name_only=&limit=` | 필요 | 2 | 구현 — 독음 역검색, 글자 조회 시 호환한자 계열 함께 반환 |
| GET | `/api/v1/hanja/{codepoint}` | 필요 | 2 | 구현 — 상세(독음·획수·이체자·비공식 힌트·공식 판정) |
| GET | `/api/v1/admin/data` | 필요 | 2 | 구현 — 데이터 현황·출처·데이터 버전(체크섬) |
| POST | `/api/v1/saju/calculate` | 필요 | 3 | 구현 — 양력/음력(윤달), 정확 시각·시간 범위·시간 미정, 진태양시·자시 옵션, 구간별 4주·오행 개수·변경 기둥·인근 절입 시각. 입력 저장·로그 없음 |
| GET | `/api/v1/calendar/solar-terms?year=` | 필요 | 3 | 구현 — 해당 연도 24절기 절입 시각(UTC·지역시) — KASI 대조용 |
| 기타 §18 엔드포인트 | | 필요 | 4~11 | 미구현 |

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
