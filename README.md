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

## 빠른 시작 (Windows PowerShell 기준)

요구: Python 3.12+ (개발 환경 3.14), Node.js 24.

```powershell
python -m venv .venv
.venv\Scripts\python scripts\tasks.py setup     # pip + npm ci
.venv\Scripts\python scripts\tasks.py fetch-unihan  # Unicode Unihan 원천 파일 (최초 1회)
.venv\Scripts\python scripts\tasks.py import-data   # 출처·한자·성씨 데이터 적재
.venv\Scripts\python scripts\tasks.py dev       # API 127.0.0.1:8000 + Web 127.0.0.1:3000
```

- 웹: http://127.0.0.1:3000 · 헬스체크: http://127.0.0.1:8000/api/v1/health
- 최초 실행 시 `var/local_token`(로컬 인증 토큰)과 `var/namecraft.db`(SQLite)가 생성됩니다. `var/`는 Git에 포함되지 않습니다.
- macOS/Linux: `.venv/bin/python scripts/tasks.py ...`

### 공식 인명용 한자표

대법원 인명용 한자표를 직접 받아 검토한 뒤 정규화 CSV(`hanja,reading,effective_date,legal_basis`)로 만들어 가져옵니다. 적재 전까지 모든 한자의 법적 허용 여부는 **판정 불가**로 표시됩니다.

```powershell
.venv\Scripts\python scripts\tasks.py import-official path\to\official.csv
```

### 테스트

```powershell
.venv\Scripts\python scripts\tasks.py test        # pytest + vitest + tsc
.venv\Scripts\python scripts\tasks.py build-web   # Next.js 프로덕션 빌드
```

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
scripts/tasks.py           로컬 작업 실행기
```
