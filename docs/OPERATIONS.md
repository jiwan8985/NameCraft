# 운영 안내 (OPERATIONS)

> 개인용 로컬 실행 기준. 버전 1.0.0rc1.

## 1. 설치·실행 (Windows PowerShell)

```powershell
python -m venv .venv                                   # Python 3.12 이상 (개발 환경 3.14)
.venv\Scripts\python scripts\tasks.py setup            # pip 고정 버전 + npm ci
.venv\Scripts\python scripts\tasks.py fetch-unihan     # Unicode Unihan 원천(최초 1회, 약 8MB)
.venv\Scripts\python scripts\tasks.py import-data      # DB 마이그레이션 + 출처·한자·성씨 적재
.venv\Scripts\python scripts\tasks.py dev              # API 127.0.0.1:8000 + 웹 127.0.0.1:3000
```

- 웹: http://127.0.0.1:3000 · 종료: 터미널에서 Ctrl+C
- Docker(선택): `docker compose up --build` — 데이터는 `namecraft-var` 볼륨에 저장
- 데이터 위치: `var/namecraft.db`(DB), `var/uploads/`(업로드), `var/local_token`(로컬 토큰). `var/` 는 Git 에 포함되지 않음.

## 2. 데이터 관리

| 작업 | 방법 |
|---|---|
| 공식 인명용 한자표 적재 | 대법원 자료를 검토해 정규화 CSV(`hanja,reading,effective_date,legal_basis`)로 만든 뒤 `tasks.py import-official <파일>` |
| Unihan 갱신 | `tasks.py fetch-unihan` → `import-data` (기존 레코드 교체, 데이터 버전·체크섬 기록) |
| 프로젝트 백업 | 화면 `/reports` → 프로젝트 JSON / 전체 백업. 무결성 확인값 포함. 평문이므로 안전한 곳에 보관 |
| 복원 | `/reports` → 복원(항상 새 프로젝트로, 변조 시 거부) |
| 삭제 | 프로젝트 삭제 또는 `DELETE ALL` 입력 후 전체 사용자 데이터 삭제(참조 데이터는 유지) |
| AI 사용량 기록 보존 | `/ai/settings` 보존 기간(기본 180일) → 지금 정리 |
| 만세력 기준값 대조 | `docs/KASI_VERIFICATION.md` 체크리스트 → `datasets/golden-tests/saju.yaml` 상태 갱신 |

## 3. 업그레이드

1. 코드 갱신 후 `tasks.py setup`(의존성) → `tasks.py migrate`(DB 스키마, Alembic). 마이그레이션 전 `/reports` 에서 전체 백업 권장.
2. `tasks.py test` 로 확인.

## 4. AI 연결 (선택)

| Provider | 설정 |
|---|---|
| Ollama | `/settings` 에서 사용하기 + 모델 이름. 생성 모델이 필요(임베딩 전용 모델은 생성 불가). 주소는 로컬만 허용 |
| Claude Code / Antigravity | 기본 꺼짐. 켜려면 `/settings` 에서 실행 명령 지정(예: `wsl.exe -e /home/<사용자>/.local/bin/claude`) 후 사용하기. 구독 한도를 사용하며 외부 전송 전 동의 창이 뜸. 각 서비스 약관은 사용자가 확인 |

AI 를 모두 꺼도 생성·분석·비교·저장이 모두 동작한다.

## 5. 문제 해결

| 증상 | 확인 |
|---|---|
| 화면에 "API 서버에 연결할 수 없습니다" | API 가 실행 중인지(`http://127.0.0.1:8000/api/v1/health`), `var/local_token` 존재 여부 |
| 헬스체크 `db_not_migrated` 경고 | `tasks.py migrate` |
| 한자 검색 결과 없음 | `tasks.py import-data` 실행 여부(`/admin/data` 한자 수 확인) |
| 개발 서버를 끈 뒤 포트가 남음(Windows) | 작업 관리자에서 해당 python/node 프로세스 종료, 또는 `taskkill /T /F /PID <번호>` |
| 출생신고 점검이 항상 '공식 재확인 필요' | 공식 인명용 한자표 미적재 — 정상 동작 |

## 6. 개인정보 원칙 (요약)

- 접근 로그에는 라우트 틀·상태·시간만 기록(이름·날짜·ID·쿼리 없음).
- 출생정보·가족·메모는 외부로 보내지 않는다. 외부 AI 는 사용자가 켜고 매번 동의할 때만, 정해진 필드만.
- 브라우저·서비스워커는 개인 데이터를 캐시하지 않는다.
