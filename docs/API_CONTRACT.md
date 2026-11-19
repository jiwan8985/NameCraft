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
| 기타 §18 엔드포인트 | | 필요 | 2~11 | 미구현 |

## 웹 프록시

브라우저는 `/api/proxy/<path>` → `/api/v1/<path>`로 호출한다. 변경 메서드는 `x-namecraft-request: 1` 헤더 필수. 프록시 자체 오류 코드: `cross_site_request`, `csrf_header_missing`, `invalid_path`, `api_token_missing`(503), `api_unreachable`(502).
