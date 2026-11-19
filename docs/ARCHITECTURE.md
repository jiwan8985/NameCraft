# 아키텍처 (ARCHITECTURE)

> 기획서 §17, §25 기준. Phase 1 시점 구현 상태를 반영한다.

## 1. 구성

```text
브라우저 ──▶ Next.js 16 (apps/web, 127.0.0.1:3000)
               │  /api/proxy/*  (서버 측 프록시: 로컬 토큰 첨부, CSRF·교차 출처 차단)
               ▼
           FastAPI (apps/api/namecraft_api, 127.0.0.1:8000, /api/v1)
               │
               ▼
           namecraft 코어 패키지 (backend/namecraft)
             ├─ config / errors / logging_safe / provenance
             ├─ auth           로컬 단일 사용자 토큰
             ├─ db             SQLAlchemy 2 + Alembic (SQLite 기본, PostgreSQL 호환)
             └─ ai_gateway     AIProvider / UsageCollector 프로토콜 + Phase 1 mock
```

## 2. 디렉터리

| 경로 | 역할 |
|---|---|
| `apps/web/` | Next.js App Router, Tailwind v4, shadcn/ui 방식 컴포넌트(`src/components/ui`) |
| `apps/api/namecraft_api/` | FastAPI 앱 팩토리(`create_app`), 라우터 |
| `backend/namecraft/` | 도메인·서비스·어댑터·DB. 이후 Phase에서 `domain/`(calendar, saju, hanja, numerology, onomastics), `services/`, `adapters/` 추가 |
| `backend/namecraft/db/migrations/` | Alembic 마이그레이션 |
| `backend/tests/` | pytest |
| `datasets/` | 출처 manifest, golden tests, DEMO fixtures |
| `scripts/tasks.py` | 로컬 작업 실행기(make 대체) |
| `docker/`, `docker-compose.yml` | 선택적 컨테이너 실행 |

`packages/contracts`, `packages/design-system`은 필요해지는 Phase(공유 타입 생성 시)에 추가한다 — 현재 OpenAPI는 `/api/v1/openapi.json`에서 생성된다.

## 3. 보안 경계 (Phase 1)

- API·웹 모두 `127.0.0.1` 바인딩. Docker도 호스트 `127.0.0.1`에만 포트 공개.
- `/api/v1/health` 외 모든 API는 `Authorization: Bearer <var/local_token>` 필요.
- 토큰은 Next 서버 프록시만 읽는다. 브라우저 JS·HTML에 노출되지 않는다.
- 프록시: `Sec-Fetch-Site`가 교차 출처면 403, 변경 메서드는 `x-namecraft-request: 1` 헤더 필수, 경로 문자 허용목록.
- 검증 오류 응답에 입력 원문을 되돌리지 않는다(위치·유형만).
- 로그 필터가 날짜·시각·Bearer 토큰·민감 키를 마스킹(안전망).

## 4. 런타임 버전 (D-003 갱신)

| 구성 | 버전 | 비고 |
|---|---|---|
| Python | 3.14.6 (Windows) | WSL Python 3.12에는 pip/venv가 없음. `requirements.lock`으로 고정 |
| Node.js | 24.15.0 (Windows `D:\nodejs`) | npm 사용(코어팩 pnpm은 추가 다운로드 필요해 미사용) |
| Next.js | 16.4.6 | Turbopack |
| React | 19.3.1 | |
| TypeScript | 5.9.3 | TS 7(네이티브)은 Next 빌드 호환성 확인 전까지 보류 |
| FastAPI / SQLAlchemy / Alembic | 0.165 / 2.1 / 1.20 | |
