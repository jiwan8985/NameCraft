# 운영 안내 (OPERATIONS)

> 개인용 로컬 실행 기준. 버전 1.0.0rc1.

## 1. 설치·실행 — 명령어 모음 `namecraft`

저장소 폴더에서 `namecraft <명령>`(명령 프롬프트) · `.\namecraft <명령>`(PowerShell) · `./namecraft <명령>`(WSL·macOS). 명령 없이 `namecraft` 는 번호 메뉴, `namecraft help` 는 전체 목록.
실제 동작은 모두 `scripts/tasks.py` 에 있고 `namecraft.cmd`·`namecraft` 는 가상환경 python 으로 그것을 실행하는 얇은 실행 파일이다(가상환경이 없으면 만든다).

```powershell
namecraft install     # 의존성(pip 고정 버전 + npm ci) → Unihan 원천(없을 때만, 약 8MB) → DB 마이그레이션·데이터 적재
namecraft start       # API 127.0.0.1:8000 + 웹 127.0.0.1:3000 (이미 포트를 쓰고 있으면 시작하지 않고 안내)
namecraft stop        # 남은 이 프로젝트 서버만 종료(다른 프로그램은 건드리지 않음)
namecraft status      # API·웹 실행 여부, DB 리비전·크기, 한자·성씨·공식 규칙 수, 프로젝트·후보·업로드 수, AI 켜짐/꺼짐
namecraft open        # 브라우저로 대시보드
```

- 웹: http://127.0.0.1:3000 · 종료: 터미널에서 Ctrl+C (창을 그냥 닫았으면 `namecraft stop`)
- Docker(선택): `docker compose up --build` — 데이터는 `namecraft-var` 볼륨에 저장
- 데이터 위치: `var/namecraft.db`(DB), `var/uploads/`(업로드), `var/local_token`(로컬 토큰). `var/` 는 Git 에 포함되지 않음.

## 2. 데이터 관리

| 작업 | 방법 |
|---|---|
| 공식 인명용 한자표 적재 | 대법원 자료를 검토해 정규화 CSV(`hanja,reading,effective_date,legal_basis`)로 만든 뒤 `namecraft import-official <파일>` |
| Unihan 갱신 | `namecraft fetch-unihan` → `namecraft import-data` (기존 레코드 교체, 데이터 버전·체크섬 기록) |
| 프로젝트 백업 | 화면 `/reports` → 프로젝트 JSON / 전체 백업. 무결성 확인값 포함. 평문이므로 안전한 곳에 보관 |
| 파일 백업 | `namecraft backup-db` → `backups/<시각>/`(DB 온라인 백업 + 업로드 폴더). 되돌리기: `namecraft stop` 후 `var/` 의 파일을 교체 |
| 복원 | `/reports` → 복원(항상 새 프로젝트로, 변조 시 거부) |
| 삭제 | 프로젝트 삭제 또는 `DELETE ALL` 입력 후 전체 사용자 데이터 삭제(참조 데이터는 유지) |
| AI 사용량 기록 보존 | `/ai/settings` 보존 기간(기본 180일) → 지금 정리 |
| 만세력 기준값 대조 | `docs/KASI_VERIFICATION.md` 체크리스트 → `datasets/golden-tests/saju.yaml` 상태 갱신 |

## 3. 업그레이드

1. `namecraft backup-db` 로 백업 → 코드 갱신 → `namecraft setup`(의존성) → `namecraft migrate`(DB 스키마, Alembic).
2. `namecraft test` 로 확인.

## 4. AI 연결 (선택)

| Provider | 설정 |
|---|---|
| Ollama | `/settings` 에서 사용하기 + 모델 이름. 생성 모델이 필요(임베딩 전용 모델은 생성 불가). 주소는 로컬만 허용 |
| Claude Code / Antigravity — 이 PC | 기본 꺼짐. Windows PATH 또는 WSL 에 설치돼 있으면 자동으로 찾음 → `/settings` 에서 **사용하기 → 연결 시험** |
| Claude Code / Antigravity — 연결 브리지 | CLI 가 다른 곳(WSL·다른 PC)에 있을 때. 그 컴퓨터에서 `namecraft bridge`(다른 PC 는 `bridge/namecraft_bridge.py` 파일만 복사해 `python3 namecraft_bridge.py --lan`) → 화면의 주소·토큰을 `/settings` › 연결 방식 '연결 브리지' 에 입력 → 사용하기 → 연결 시험. 브리지는 정해진 두 CLI 만 실행하고 토큰 없는 요청을 거부. 다른 PC 연결은 같은 네트워크에서만 |

구독 한도를 사용하며, 이름 생성 시 보낼 내용을 먼저 보여 주고 동의를 받는다. 각 서비스 약관은 사용자가 확인한다.

AI 를 모두 꺼도 생성·분석·비교·저장이 모두 동작한다.

## 5. 문제 해결

| 증상 | 확인 |
|---|---|
| 화면에 "API 서버에 연결할 수 없습니다" | API 가 실행 중인지(`http://127.0.0.1:8000/api/v1/health`), `var/local_token` 존재 여부 |
| 헬스체크 `db_not_migrated` 경고 | `namecraft migrate` |
| 한자 검색 결과 없음 | `namecraft status` 의 한자 수 확인 → 0 이면 `namecraft import-data` |
| `namecraft start` 가 "포트가 이미 사용 중" | 이전 서버가 남은 것 — `namecraft stop` 후 다시 `namecraft start` |
| 상태가 궁금할 때 | `namecraft status` |
| 출생신고 점검이 항상 '공식 재확인 필요' | 공식 인명용 한자표 미적재 — 정상 동작 |

## 6. 개인정보 원칙 (요약)

- 접근 로그에는 라우트 틀·상태·시간만 기록(이름·날짜·ID·쿼리 없음).
- 출생정보·가족·메모는 외부로 보내지 않는다. 외부 AI 는 사용자가 켜고 매번 동의할 때만, 정해진 필드만.
- 브라우저·서비스워커는 개인 데이터를 캐시하지 않는다.
