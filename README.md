# NameCraft AI

출생 예정 아동의 작명부터 기존 이름 분석·비교·최종 선정까지 지원하는 **검증 가능한** 개인용·로컬 우선 작명 플랫폼.

- SSOT 기획서: [`NameCraft_AI_MASTER_PLAN_v2.1.md`](NameCraft_AI_MASTER_PLAN_v2.1.md)
- 진행 현황: [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md) · 아키텍처: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · API: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

## 현재 상태
**1.0.0rc1 (출시 후보)** — Phase 0~12 구현 완료. 남은 일은 사용자 확인 항목(KASI 대조·공식 인명용 한자표 등)과 브라우저 E2E입니다: [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)
운영 안내 [`docs/OPERATIONS.md`](docs/OPERATIONS.md) · 위협 모델 [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) · 성능 [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)

## 원칙 요약
- 법적 사실 · 결정론적 계산 · 전통 해석 · 주관/AI 평가를 분리 표시합니다.
- AI는 후보 제안과 설명에만 사용하며, 한자 허용·획수·사주 계산을 대신하지 않습니다.
- AI(Ollama / Claude Code / Antigravity)는 선택 기능입니다. 유료 API 키 입력·종량제 연결은 제공하지 않습니다.
- 이름 해석은 문화적 참고 자료이며 건강·성공·운명을 보증하지 않습니다.

## 빠른 시작 — 명령어 모음 `nc`

요구: Python 3.12+, Node.js 24. 저장소 폴더에서 실행합니다.

| 환경 | 쓰는 법 |
|---|---|
| Windows 명령 프롬프트 | `nc <명령>` |
| Windows PowerShell | `.\nc <명령>` |
| WSL · macOS · Linux | `./nc <명령>` |

명령 없이 `nc` 만 입력하면 **번호로 고르는 메뉴**가 나옵니다(번호 뒤에 `?` 를 붙이면 설명만, 예: `2?`).

| 도움말 | 보여주는 것 |
|---|---|
| `nc help` (또는 `nc /?`) | 처음 시작하는 순서 + 전체 명령 목록 |
| `nc help <명령>` · `nc <명령> --help` | 그 명령이 하는 일, 언제 쓰는지, 예시, 주의 사항 |
| 명령을 잘못 입력하면 | 비슷한 명령 제안 (예: `nc stat` → `status`) |

```powershell
nc install     # 처음 한 번: 의존성 설치 + 한자 자료 받기 + DB 준비 (가상환경이 없으면 자동 생성)
nc start       # API + 웹 실행 → http://127.0.0.1:3000 (종료: Ctrl+C)
nc stop        # 창을 닫았는데 서버가 남아 있을 때
nc status      # 실행 상태·데이터·AI 설정 요약
```

| 분류 | 명령 |
|---|---|
| 실행 | `start` · `stop` · `open`(브라우저) · `status` |
| 데이터 | `backup-db` · `migrate` · `fetch-unihan` · `import-data` · `import-official <CSV>` |
| 검사 | `test` · `test-api [pytest 옵션]` · `test-web` · `test-security` · `build-web` · `perf` · `audit` |
| Docker | `docker-up` · `docker-down` |

- 데이터 위치: `var/namecraft.db`(DB), `var/uploads/`(업로드), `var/local_token`(로컬 토큰) — Git 에 포함되지 않습니다.
- 대법원 인명용 한자표는 검토 후 정규화 CSV(`hanja,reading,effective_date,legal_basis`)로 만들어 `nc import-official <파일>` 로 넣습니다. 적재 전까지 법적 허용 여부는 **판정 불가**로 표시됩니다.

### Docker (선택)

```bash
docker compose up --build      # 127.0.0.1:3000 / 127.0.0.1:8000
```

## 디렉터리
```
apps/web/                  Next.js UI
apps/api/                  FastAPI 엔드포인트
backend/namecraft/         코어(설정·인증·DB·AI Gateway, 이후 도메인 엔진)
backend/tests/             pytest
datasets/                  출처 manifest · golden tests · DEMO fixtures
docs/                      요구사항·규칙·출처·QA·결정·진행 현황
scripts/tasks.py           명령어 모음 본체 (nc.cmd · nc 가 실행)
```
