# NameCraft AI

출생 예정 아동의 작명부터 기존 이름 분석·비교·최종 선정까지 지원하는 **검증 가능한** 개인용·로컬 우선 작명 플랫폼.

- 프로젝트 계획: [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)
- 진행 현황: [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md) · 아키텍처: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · API: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

## 현재 상태
**1.0.0rc1 (출시 후보)** — Phase 0~12 구현 완료. 남은 일은 사용자 확인 항목(KASI 대조·공식 인명용 한자표 등)과 브라우저 E2E입니다: [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)
운영 안내 [`docs/OPERATIONS.md`](docs/OPERATIONS.md) · 위협 모델 [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) · 성능 [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)

## 원칙 요약
- 법적 사실 · 결정론적 계산 · 전통 해석 · 주관/AI 평가를 분리 표시합니다.
- AI는 후보 제안과 설명에만 사용하며, 한자 허용·획수·사주 계산을 대신하지 않습니다.
- AI 추천은 로컬 Ollama를 사용합니다.
- 이름 해석은 문화적 참고 자료이며 건강·성공·운명을 보증하지 않습니다.

## 빠른 시작

| 환경 | 방법 |
|---|---|
| Windows 명령 프롬프트 | 처음 한 번 `namecraft.cmd install` → 이후 `namecraft.cmd`를 실행하고 메뉴에서 **1번** 선택 |
| Windows PowerShell | 처음 한 번 `.\namecraft.cmd install` → 이후 `.\namecraft.cmd`를 실행하고 메뉴에서 **1번** 선택 |
| WSL · macOS · Linux | 처음 한 번 `./namecraft install` → 이후 `./namecraft`를 실행하고 메뉴에서 **1번** 선택 |

모든 명령은 저장소 폴더에서 실행합니다. 사용을 마치면 실행 창에서 `Ctrl+C`를 누르세요.

요구: Python 3.12+, Node.js 24. 명령 이름은 리눅스 기본 명령(`nc`=netcat)과 겹치지 않도록 `namecraft` 입니다.
명령을 붙이지 않고 실행하면 네 가지 작업을 번호로 고를 수 있습니다. 아래 예시의 `namecraft`는 환경에 맞게 위 표의 실행 명령으로 바꿔 입력하세요.

| 번호 | 작업 | 직접 실행 |
|---|---|---|
| 1 | 앱과 브라우저 열기 · 휴대폰 접속 켜기 | `namecraft start --open --lan` |
| 2 | 실행 상태 확인 | `namecraft status` |
| 3 | 앱 종료 | `namecraft stop` |
| 4 | 작명 데이터 백업 | `namecraft backup-db` |

메뉴에서 `1?`을 입력하면 실행 방법을 볼 수 있고, Enter만 누르면 닫힙니다.
`namecraft help`는 기본 목록, `namecraft help --all`은 설치·데이터·개발 명령을 포함한 전체 목록을 보여줍니다.
개별 명령의 사용법은 `namecraft help <명령>`으로 확인하세요.

### 휴대폰에서 열기

명령 메뉴의 **1번**으로 실행하면 휴대폰 접속이 켜집니다. PC의 홈에서 **휴대폰에서 열기**를 누르고, 같은 Wi-Fi에 있는 휴대폰 카메라로 QR을 찍으세요. QR은 현재 앱 실행에 연결되므로 앱을 다시 시작하면 새 QR을 사용합니다.

접속이 안 되면 PC와 휴대폰이 동일한 Wi-Fi에 있는지 확인하고, Windows 방화벽에서 Node.js 연결을 허용할 때는 개인 네트워크를 선택하세요. 여러 네트워크에 연결된 PC는 `NAMECRAFT_LAN_IP`로 사용할 IPv4 주소를 지정할 수 있습니다.


- 데이터 위치: `var/namecraft.db`(DB), `var/uploads/`(업로드), `var/local_token`(로컬 토큰) — Git 에 포함되지 않습니다.
- 대법원 인명용 한자표는 검토 후 정규화 CSV(`hanja,reading,effective_date,legal_basis`)로 만들어 `namecraft import-official <파일>` 로 넣습니다. 적재 전까지 법적 허용 여부는 **판정 불가**로 표시됩니다.

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
scripts/tasks.py           명령어 모음 본체 (namecraft.cmd · namecraft 가 실행)
```
