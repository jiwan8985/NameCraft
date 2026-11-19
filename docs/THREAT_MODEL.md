# 위협 모델 (THREAT_MODEL)

> 기획서 §20, §31, §22.1(보안). 대상: 개인용 로컬 실행(127.0.0.1), 단일 사용자. 작성 2026-11-19, 버전 1.0.0rc1.

## 1. 보호 대상

| 자산 | 민감도 | 저장 위치 |
|---|---|---|
| 아이 출생 예정일·시각, 가족 이름(별칭), 후보 이름·메모 | 높음 | `var/namecraft.db` |
| 업로드한 작명소 자료 | 높음 | `var/uploads/` (무작위 파일명) |
| 로컬 API 토큰 | 높음 | `var/local_token` |
| 구독형 AI 계정(Claude Code·Antigravity) | 높음 | **저장하지 않음**(각 CLI 가 관리, 앱은 읽지 않음) |
| 참조 데이터(Unihan·성씨 시드·행성력) | 낮음(공개) | DB·`datasets/` |

## 2. 신뢰 경계와 진입점

```text
브라우저 ──(127.0.0.1:3000)── Next 서버 프록시 ──(토큰 첨부, 127.0.0.1:8000)── FastAPI ── SQLite / var/uploads
                                                                         └─(사용자가 켠 경우만) 로컬 Ollama / CLI 서브프로세스
```

진입점: 웹 화면, `/api/proxy/*`, FastAPI `/api/v1/*`, 파일 업로드, AI 출력, 백업 JSON 가져오기, 붙여넣은 수동 전달 결과.

## 3. 위협과 대응 (STRIDE)

| # | 위협 | 대응 | 검증 |
|---|---|---|---|
| S1 | 같은 PC의 다른 웹사이트가 프록시를 통해 API 호출(CSRF) | 프록시: `Sec-Fetch-Site` 교차 출처 차단, 변경 메서드는 사용자 정의 헤더 필수, CORS 는 localhost 만 | `proxy-guard.test.ts`, `test_cors_rejects_foreign_origin` |
| S2 | 토큰 없이 API 직접 호출 | `/health` 외 85개 작업 전부 Bearer 토큰, 상수 시간 비교 | `test_every_api_route_requires_token_except_health`(OpenAPI 전체 열거) |
| S3 | 네트워크의 다른 기기 접근 | API·웹 모두 127.0.0.1 바인딩, Docker 도 호스트 127.0.0.1 만 공개 | 설정 확인 |
| T1 | 백업 파일 변조 후 복원 | sha256 무결성 확인, 실패 시 전부 거부, 복원은 항상 새 프로젝트 | `test_tampered_backup_rejected`, `test_full_backup_and_restore_all_or_nothing` |
| T2 | AI 출력이 판정·점수를 조작 | JSON 스키마(추가 필드 금지), 서버가 한자·독음·조건을 재검증, 설명의 금지 표현·계산 주장 제거 | `test_validation_rejects_bad_ai_output`, `test_ai_reason_html_is_stored_as_plain_text_only` |
| T3 | 업로드 문서 속 지시문(프롬프트 인젝션) | 문서 내용은 AI 로 보내지 않음, 지시문 같은 문장은 검토자에게 경고 | `test_instruction_like_text_flagged_not_executed` |
| R1 | 결정·평가 기록 부인 | 결정 이유·스냅샷·반응 시각 저장, 출생정보 버전 보존 | Phase 9 테스트 |
| I1 | 로그로 개인정보 유출 | uvicorn 기본 접근 로그 끔(쿼리·ID 노출), 라우트 틀만 기록, 날짜·시각·토큰 마스킹 필터, 오류 응답에 입력 원문 미포함 | `test_access_log_has_route_template_not_personal_data`, `test_whole_flow_logs_no_birth_or_name_data` |
| I2 | 브라우저·프록시 캐시에 개인정보 | API 응답 `Cache-Control: no-store`, 서비스워커는 `/api/` 미캐시 | `test_security_headers_and_no_store`, `phase11.test.tsx` |
| I3 | 외부 AI 로 개인정보 전송 | 기본 꺼짐, 전송 필드 미리보기·명시 동의, 성씨·출생정보·가족·메모 기본 비전송, 꺼진 Provider 는 절대 실행 안 함 | `test_external_provider_requires_consent`, `test_disabled_*` |
| I4 | 구독 인증 정보 탈취·오용 | 인증 캐시·쿠키 미접근, 서브프로세스 환경에서 유료 API 키 변수 제거, `--bare`·권한 우회 플래그 금지, 빈 임시 폴더에서 도구 없이 실행 | `test_sanitized_env_*`, `test_cli_*`, `test_code_does_not_touch_auth_caches` |
| I5 | 업로드 파일을 HTML 로 실행(XSS) | 시그니처로 형식 판별, 원본은 `nosniff`·`CSP default-src 'none'`·정확한 형식으로만 제공 | `test_upload_html_disguised_as_text_is_served_as_plain_text` |
| D1 | 큰 파일·큰 계산으로 서버 정지 | 업로드 10MB, PDF 50쪽, 시나리오 최대 15일·62일 범위, 조합 수 상한, 후보 수 상한 | 단위 테스트 |
| E1 | 경로 조작으로 다른 파일 접근 | 업로드 저장명 무작위, 저장 폴더 밖 경로 차단, 프록시 `.`/`..` 세그먼트 차단 | `test_sniff_and_filename_safety`, 프록시 테스트 |
| E2 | 원격 Ollama 로 데이터 전송 | Ollama 주소는 로컬만 허용(설정 검증) | `test_ollama_url_must_be_local` |
| B1 | 연결 브리지를 통한 임의 명령 실행 | 브리지는 claude·agy 두 CLI 와 고정 인자만 실행, 요청의 명령·옵션 무시, 금지 플래그 차단 | `test_bridge_rejects_unknown_provider_commands_and_big_bodies`, `test_bridge_args_match_backend` |
| B2 | 브리지 무단 사용(같은 네트워크의 다른 기기) | 기본 127.0.0.1 바인딩, `--lan` 은 명시 옵션+경고, Bearer 토큰(상수 시간 비교, 파일 권한 600, 재발급), 한 번에 한 요청, 64KB 제한 | `test_bridge_requires_token`, `test_bridge_token_file` |
| B3 | 브리지 토큰 유출 | 앱 DB 에만 저장, API 응답·상태에 토큰 미포함(`bridge_token_set` 만) | `test_settings_api_bridge` |
| B4 | 브리지 경유 개인정보 전송 | 일반 외부 Provider 와 같은 동의·전송 필드 제한, 브리지 로그에 내용 미기록 | `test_settings_api_bridge` |

## 4. 남은 위험 (수용 또는 사용자 조치)

| 위험 | 상태 |
|---|---|
| 같은 PC의 다른 사용자 계정·악성 프로그램이 `var/` 파일을 읽음 | 수용 — OS 계정 보호에 의존. Windows 에서는 `var/local_token` 권한을 OS ACL 로 제한하지 못함. 디스크 암호화(BitLocker) 권장 |
| DB·업로드 파일 암호화 저장 없음 | 수용(개인용 로컬). 백업 파일도 평문 JSON — 안전한 곳에 보관 |
| 다중 사용자 로그인·권한 분리 없음 | 범위 밖(P2). 공개 서비스 전 별도 설계 필요 |
| 요청 빈도 제한 없음 | 로컬 단일 사용자라 수용 |
| 브리지 통신은 HTTP(평문) | 수용 — 같은 PC·같은 네트워크 전용. 인터넷 노출 금지(문서·실행 화면 경고). 필요 시 사용자가 HTTPS 리버스 프록시 앞단 구성 |
| 개발 PC 환경변수 `NODE_TLS_REJECT_UNAUTHORIZED=0` (Windows 전역) | **사용자 조치 권장** — npm 등 Node 의 HTTPS 인증서 검증이 꺼진 상태 |
| 구독형 CLI 의 약관상 자동 실행 허용 범위 | 사용자 확인 — 기본 꺼짐 |

## 5. 의존성 점검 (2026-11-19)

- `npm audit` (운영·개발 전체): 취약점 0
- `pip-audit -r requirements.lock`: 알려진 취약점 없음
