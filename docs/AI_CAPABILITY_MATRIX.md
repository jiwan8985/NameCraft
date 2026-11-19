# AI Provider Capability Matrix

> 기획서 §29~§33 기준. Phase 0 확정 대상 산출물.
> **조사 기준일:** 2026-11-19, **조사 환경:** 개발 PC(WSL2). 로컬 설치 CLI의 `--help` 출력과 기획서 §34 공식 문서 링크를 근거로 한다.
> **주의:** 아래는 *이 PC의 설치 버전* 기준이다. Phase 7에서 런타임 탐지(`healthcheck`, 버전 핀)로 다시 판정하며, 판정이 바뀌면 이 문서를 갱신한다.

## 1. 로컬 조사 결과

| Provider | 설치 | 버전 | 확인된 공식 비대화형 인터페이스 | 비고 |
|---|---|---|---|---|
| Ollama | **미설치**(WSL PATH 기준) | — | 공개 로컬 HTTP API(`/api/tags`, `/api/generate`, `/api/chat`, `/api/version`) — 공식 문서 | Windows 측 설치 여부는 사용자 확인 필요 |
| Claude Code | 설치 (`~/.local/bin/claude`) | 2.1.328 | `claude -p/--print` 비대화형 출력, `--output-format`(text/json/stream-json), `--model`, `--fallback-model` | `--bare` 모드는 OAuth를 읽지 않고 **API 키만** 사용 → **사용 금지**(§33.1) |
| Antigravity | 설치 (`~/.local/bin/agy`) | 1.5.9 | `agy -p/--print`, `--output-format`(text/json/stream-json), `--json-schema`, `--model`, `--print-timeout`, `agy models`, `agy acp`(Agent Client Protocol stdio) | `/usage`·`/quota`는 대화형 슬래시 명령 |

## 2. Capability 판정 (초기)

판정 값: `supported`(공식 인터페이스 확인) / `conditional`(공식이나 사용자 설정·동의·버전 확인 필요) / `manual`(사용자 수동 입력/화면 열기) / `not_supported`(공식 경로 없음) / `n/a`

| Capability | Ollama | Claude Code | Antigravity |
|---|---|---|---|
| `healthcheck` | supported (`/api/version`) | supported (`claude --version`, 설치·버전만) | supported (`agy --version`) |
| `list_models` | supported (`/api/tags`) | conditional (`--model` 별칭 고정 목록, 동적 목록 공식 경로 미확인) | supported (`agy models`) — 출력 스키마 버전 확인 필요 |
| `generate_candidates` | supported | conditional — `claude -p --output-format json` | conditional — `agy -p --output-format json --json-schema` |
| `explain_name` | supported | conditional (동일) | conditional (동일) |
| `summarize_comparison` | supported | conditional (동일) | conditional (동일) |
| `observe_usage` (NameCraft 내부) | supported (응답의 `eval_count`, `prompt_eval_count`, `total_duration` 등) | conditional — JSON 출력에 포함된 사용량 메타데이터만(필드는 버전별 스키마 테스트) | conditional — JSON 출력 메타데이터만(버전별 확인) |
| `observe_usage` (계정 전체) | n/a | manual — 공식 `/usage` 화면 값 사용자 입력. 상태줄/훅 입력의 한도 필드는 **설치 버전 문서 확인 후** conditional로 승격 | manual — 공식 `/usage`(`/quota`) 화면 값 사용자 입력 |
| `observe_quota` (5h/주간/모델 그룹) | n/a (로컬, 한도 없음) | manual (위와 동일) | manual (위와 동일) |

### 기본 실행 모드 결정

| Provider | 기본 모드 | 조건부 승격 | 폴백 |
|---|---|---|---|
| Ollama | `native_local` | — | 규칙 기반 |
| Claude Code | `manual_handoff` | 사용자가 명시적으로 활성화 + 설치·로그인 확인 + 전송 필드 동의 → `supported_cli_task` (`claude -p`) | `manual_handoff` → 규칙 기반 |
| Antigravity | `manual_handoff` | 동일 조건 → `supported_cli_task` (`agy -p`) | `monitor_only`/`manual_handoff` → 규칙 기반 |

**근거:** 두 CLI 모두 공식 `--print` 비대화형 모드를 제공하므로 *사용자 PC에서 사용자가 직접 켠 경우* 로컬 백엔드가 서브프로세스로 실행하는 것은 공식 인터페이스 사용이다. 그러나 (1) 구독 이용약관상 제3자 앱 자동화 허용 범위, (2) 원격 배포 시 사용 불가, (3) 한도 소모 가능성 때문에 **기본값은 비활성(`manual_handoff`)** 으로 둔다. → `DECISIONS.md` D-004.

## 3. 금지 사항 (테스트로 강제)

- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY` 등 유료 API 키를 읽거나 서브프로세스 환경에 주입하지 않는다(서브프로세스 실행 시 해당 변수 **제거**).
- `claude --bare` 사용 금지.
- `~/.claude/`, `~/.gemini/`, Antigravity 인증 캐시, 브라우저 쿠키 등 인증 저장소 파일을 읽지 않는다.
- 비공개 엔드포인트 호출, 화면 스크래핑, 대화형 TUI 자동 조작(pty 주입)으로 `/usage` 수집하지 않는다.
- `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions` 사용 금지. 이름 생성 작업은 도구 사용 없는 순수 텍스트 작업으로 제한(Phase 7에서 허용 도구 0개 설정 검증).

## 4. 사용량 지표 정의 (`metric_key`)

| metric_key | 단위 | 의미 | 적용 Provider | source_kind |
|---|---|---|---|---|
| `nc.requests` | count | NameCraft가 발생시킨 AI 요청 수 | 전체 | `local_observed` |
| `nc.success_rate` | ratio | NameCraft 요청 성공률 | 전체 | `local_observed` |
| `nc.latency_ms` | ms | 요청~응답 시간 | 전체 | `local_observed` |
| `nc.tokens_in` / `nc.tokens_out` | tokens | Provider가 응답에 보고한 토큰 수 | Ollama(제공), CLI(출력에 있을 때만) | `local_observed` / `unknown` |
| `ollama.eval_rate` | tokens/s | 생성 속도 = eval_count / eval_duration | Ollama | `local_observed` |
| `quota.used_pct` | percent | 공식 화면/인터페이스의 사용률 | Claude Code, Antigravity | `official` 또는 `manual` |
| `quota.reset_at` | timestamp | 한도 초기화 시각 | Claude Code, Antigravity | `official` 또는 `manual` |
| `quota.remaining` | provider-native | 모델 그룹별 잔여량(단위는 Provider 원본 그대로) | Antigravity | `official` 또는 `manual` |
| `subscription.fee_monthly` | KRW/USD | 사용자가 입력한 정액 구독료(선택) | Claude Code, Antigravity | `manual` |

**규칙:** 서로 다른 `metric_unit`은 합산·환산하지 않는다. `nc.*`는 계정 전체 사용량이 아니다. `quota.*`가 없으면 `unknown` 상태로 저장하고 숫자를 생성하지 않는다.

## 5. 데모 데이터

`datasets/fixtures/ai-usage-demo.json` — 모든 레코드 `is_demo: true`, `source_kind: demo`. 운영 DB 시드에 포함 금지(Phase 11 테스트: 데모 플래그가 있는 레코드가 실제 집계에 섞이면 실패).

## 6. 사용자 확인 필요

- [ ] Windows 측 Ollama 설치 여부 및 사용할 모델(예: 한국어 가능 모델)
- [ ] Claude Code / Antigravity CLI 실행 연동을 실제로 켤지(기본 꺼짐) — 각 서비스 약관은 사용자가 최종 확인
