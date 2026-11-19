# 설계 결정 기록 (DECISIONS)

형식: `D-번호 | 날짜 | 결정 | 근거 | 상태(proposed/accepted/superseded)`

| ID | 날짜 | 결정 | 근거 | 상태 |
|---|---|---|---|---|
| D-001 | 2026-11-19 | 저장소 루트(`NameCraft/`)를 기획서 §25의 `namecraft-ai/` 루트로 사용 | 기존 Git 저장소 유지 | accepted |
| D-002 | 2026-11-19 | 개인용 기본 DB는 SQLite, 스키마는 PostgreSQL 호환으로 작성(Alembic) | 기획서 §17 | accepted |
| D-003 | 2026-11-19 | ~~Python 3.12 + pnpm~~ → D-010으로 대체 | | superseded |
| D-004 | 2026-11-19 | Claude Code·Antigravity 기본 모드 `manual_handoff`(꺼짐). 사용자가 명시적으로 켜면 공식 `-p/--print` 비대화형 모드로 로컬 실행 | 공식 CLI 기능 존재하나 약관·한도·민감정보 고려(§29.1, §33.1) | accepted |
| D-005 | 2026-11-19 | 계정 전체 구독 사용량/한도는 기본 `manual` 입력. 자동 수집은 공식·문서화된 인터페이스가 버전별로 확인될 때만 | §30.2, §30.6 | accepted |
| D-006 | 2026-11-19 | Golden Test 기대값에 `definitional/formula_derived/externally_verified/pending` 상태 부여 | §21.1 "임의 데이터로 통과 금지" | accepted |
| D-007 | 2026-11-19 | 음령오행은 `modern-common`(기본)과 `hunmin-haerye` 두 학파 프로필 제공 | 실제 학파 차이 존재, 일치도 기능의 기준 | accepted |
| D-008 | 2026-11-19 | 공식 데이터는 기본 수동 다운로드 + 체크섬, 원천 파일은 Git 미포함 | 재배포 조건 미확인(§5.2, §26) | accepted |
| D-009 | 2026-11-19 | 외부 CI 미사용, 로컬 일괄 실행 `python scripts/tasks.py test` (WSL·Windows 모두 make 미설치) | 기획서 Phase 1 | accepted |
| D-010 | 2026-11-19 | 런타임: Windows Python 3.14.6 venv(`.venv`) + Windows Node 24.15 + npm. WSL 측 uv/Node 사용자 영역 설치는 보류(자동 설치 권한 미허용) | 기존 설치 도구만으로 구성, 프로젝트가 D: 드라이브에 있어 Windows 툴체인이 자연스러움 | accepted |
| D-011 | 2026-11-19 | 로컬 인증: 단일 사용자 무작위 토큰(`var/local_token`) + Next 서버 프록시가 토큰 첨부, 브라우저 비노출. 프록시는 교차 출처·CSRF 헤더 검사 | §20, §31.2 | accepted |
| D-012 | 2026-11-19 | TypeScript 5.9 고정(TS 7 네이티브는 Next 16 빌드 호환성 확인 전 보류) | 빌드 안정성 | accepted |

## Open Questions (사용자 결정 필요)

1. ~~Docker 사용 여부~~ → 스크립트 기본 + Compose 선택 제공 (Phase 1 반영)
2. ~~Node 실행 위치~~ / 3. ~~Python 패키지 관리~~ → D-010
4. **Ollama:** Windows 측 설치 여부와 기본 모델.
5. **81수리·원획 기준 문헌:** 기본 프로필에 사용할 문헌/학파.
6. **공식 데이터 이용조건 확인:** `DATA_SOURCES.md` §4 체크리스트.
