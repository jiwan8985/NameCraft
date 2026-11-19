# Phase 진행 현황 (PHASE_STATUS)

| Phase | 목표 | 상태 | 커밋 | 비고 |
|---|---|---|---|---|
| 0 | 요구사항 확정·레퍼런스 확보 | 완료(승인됨) | b224e69 | |
| 1 | Monorepo/기반 환경 | 완료(승인됨) | 3a72eea | |
| 2 | 성씨·한자·어휘 DB | 승인됨 — 공식 인명용 한자표 적재 대기 | d510795 | |
| 3 | 만세력·사주 엔진 | 승인됨 — KASI 대조는 최종 단계(D-022) | ca2d95f | |
| 4 | 전통 성명학 | 승인됨 | 88be2df | |
| 5 | 언어·의미 평가 | 승인됨 | 131c9db | |
| 6 | 생성/역검색 | 승인됨 | a47a58f | |
| 7 | 다중 AI·랭킹 | **완료 보고(승인 대기)** | (이 커밋) | 아래 상세 |
| 8 | 상세 분석/비교 | 대기 | | |
| 9 | 시뮬레이션/공동 선택 | 대기 | | |
| 10 | 자료 교차검증·최종 점검 | 대기 | | |
| 11 | 보고서·PWA·백업·AI 관제 | 대기 | | |
| 12 | 성능·보안·출시 | 대기 | | |

## 최종 단계 사용자 확인 항목 (D-022)

| 항목 | 관련 Phase | 문서 |
|---|---|---|
| KASI 절기·음양력 11개 대조 | 3 | `docs/KASI_VERIFICATION.md` |
| 대법원 인명용 한자표 확보·정규화 CSV 적재 | 2 | `docs/DATA_SOURCES.md` §4 |
| 81수리 분류를 실제 문헌/작명소 자료와 대조(선택) | 4 | `datasets/rules/luck81-kr-common.yaml` |
| JPL 행성력 이용조건 재확인(상용화 전) | 3 | `datasets/source-manifests/SRC-JPL-DE.yaml` |

## Phase 7 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| Ollama 어댑터 | 실제 탐지(생성/임베딩 모델 구분), `/api/chat` JSON 스키마 강제·seed, 토큰·시간 기록 |
| Claude Code / Antigravity 어댑터 | 사용자 지정 명령·버전 탐지, 기본 비활성, 공식 비대화형 모드(도구 없음/plan·sandbox), 빈 폴더, API 키 환경변수 제거, 한도·로그인 오류 구분 |
| 실행/관찰 분리 | 상태 확인(`status_only`)과 생성 호출 분리, 호출마다 `ai_invocations` 기록(provider·mode·model·source_type·quota_data_status) |
| 동의·전송 범위 | 전송 필드 미리보기(`dry_run`), 외부 Provider 사전 동의, 민감 정보 비전송 |
| AI 응답 검증 | 스키마 → 서버 재검증(한글·하드 조건·인명용 독음·비속어) → 금지 표현·계산 주장 제거 |
| 폴백 | 미설치·모델 없음·비활성·시간 초과·한도·잘못된 출력 → 허용된 대체 → 규칙 기반 |
| 수동 전달 | 붙여넣기용 프롬프트 + 결과 JSON 가져오기 |
| 재현성 | 생성 기록(모델·프롬프트 버전·시드·보낸 필드 이름·검증 결과), AI 미사용 시 결정론 |
| 저장 | 프로젝트·후보·반응 테이블(마이그레이션 0003) |
| 취향 학습 | 좋아요/싫어요 → 스타일·음절 프로필, 싫어요 = 제외(해제 가능), 다음 생성에 반영 |
| 랭킹 | 6항목 가중치(25/20/20/15/15/5) 정규화, N/A 재정규화, 유효성 gate 분리, 신뢰도 4축, 항목별 정렬 |

### 완료 게이트: "공식 연동 범위 검증 · AI 응답 검증 · 폴백 · 재현성" — 충족(자동 테스트 기준)
| 항목 | 결과 |
|---|---|
| 공식 범위 | 금지 플래그 차단, 도구 없는 실행, 빈 작업 폴더, API 키 제거, 비활성 시 실행 안 함, 동의 전 실행 안 함 — 가짜 CLI로 검증 |
| 응답 검증 | 잘못된 한글·중복·음절 수·독음 환각·비속어·점수 필드·금지 표현 차단 |
| 폴백 | 모델 없음·잘못된 JSON·한도 → 규칙 기반, 자동 대체는 허용된 Provider 만 |
| 재현성 | 기록 필드 저장, AI 없음 경로 동일 결과 |
| 실제 환경 | Ollama phi4-mini 생성 1회 성공(검증에서 1건 거부), Claude Code·Antigravity 는 `wsl.exe` 경유 버전 확인만(연동 꺼짐) |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 7 신규: AI 게이트웨이 22, 프로젝트·랭킹·AI API 9, 회귀 1) | 190 | 0 |
| vitest | 10 | 0 |

### 알려진 문제 / 메모
- 설치된 Ollama 모델(phi4-mini, qwen2.5-coder)은 한국어 이름 제안 품질이 낮음 — 한국어 지원이 좋은 instruct 모델을 받으면 개선(사용자 선택).
- Claude Code·Antigravity 실제 생성 호출은 하지 않음(연동 꺼짐 기본값, 구독 한도 소모 방지). 켤 때 `PATCH /ai/preferences` 로 `command`·`enabled` 지정.
- 개발 중 발견·수정: `name_type=any` 에서 한자 조합 없는 후보가 결과에서 빠지던 버그(회귀 테스트 추가), 시스템 프롬프트 문구가 금지 표현 검사에 걸린 문제.
- 사주 항목은 기본 N/A. 부모 공동 평가·토너먼트는 Phase 9.

### 다음 Phase(8) 준비 사항
- 상세 분석/비교 UI: `/projects/new`(3단계 입력), `/projects/:id/recommendations`(카드·필터·정렬·근거·재생성·반응), `/names/analyze`, `/names/:id`, `/compare`(레이더 차트), AI Provider 선택 UI. 완료 게이트 "모든 점수 근거 조회 가능" + "모델 선택→검증→추천 결과 흐름 E2E"(§32).

## Phase 6 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구(§8) | 구현 |
|---|---|
| 규칙 기반 생성 (AI 장애 시 기본) | 음절 사전 조합 + 하드 필터 + 발음 루브릭, 2단계 선별 |
| 기존 데이터 기반 | 한글 이름 예시 + 좋아한 이름 스타일 유사 — 공개 통계 없어 **제한적** |
| AI 기반 | Phase 7 |
| 이름 역검색 | 한글 → 인명용 독음 한자 → 공식 판정 → 조합별 획수·수리·뜻 주의 → 정렬 |
| 한자 조합 최적화 | 가중치 조정 가능한 정렬 점수, 구성요소·미계산 항목 공개 |
| 대체 한자 추천 | 글자별 우려 사항 + 점수가 개선되는 대안 |
| 유사 스타일 확장 | 좋아한 이름의 음운 특징(유성음·열린 음절·밝은 모음·길이)과 가까운 **다른** 후보 |
| 강제 필터 | 제거(하드 조건) / 격리(비속어 정확 일치) / 보류(공식 미확인) / 차단(공식 미수록) |
| 중복 제거·다양성 | 유사도 임계값, 첫·끝 음절 개수 제한 |
| API | `POST /names/generate`, `/names/reverse-search`, `/names/alternative-hanja` |

### 완료 게이트: "AI 없어도 후보 생성 · 무효 후보 차단" — 충족
| 항목 | 결과 |
|---|---|
| AI 없이 생성 | 대표 시나리오(심씨 여아, 선호 예시 8개)에서 20개 생성 2.8초, 같은 입력 → 같은 결과 |
| 무효 후보 차단 | 하드 조건 위반 제거, 인명용 독음 한자 없는 한자 이름 제외, 공식 미수록 글자 조합 `rejected`, 비속어 정확 일치 격리 — 테스트로 검증 |
| 미확인 구분 | 공식 자료 없으면 `passed` 0건, 모두 `on_hold` |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 6 신규: 생성·역검색 13, API 3) | 164 | 0 |

### 알려진 문제 / 메모
- **한자 뜻의 질**을 판단할 데이터가 없음: 정렬 점수가 같은 조합(예: 只亞·志亞)을 뜻으로 구분하지 못함. 영어 풀이 주의 키워드만 반영(굶주릴 餓 등). → Phase 7 AI 해설 또는 국립국어원 자료로 보강.
- 음절 사전이 작아(84개) 결과가 비슷한 결로 모일 수 있음 — 취향 학습(Phase 7)과 공개 통계로 개선 예정.
- 후보 저장/복원은 Phase 7 (D-027).
- 3음절 이름 후보 풀이 28만 개라 2단계 선별(상위 4,000)로 제한 — 일부 조합은 검토되지 않음.

### 다음 Phase(7) 준비 사항
- 다중 AI·랭킹: Ollama·Claude Code·Antigravity 어댑터(실제 탐지·공식 CLI 비대화형 실행·전송 동의), AI 응답 스키마 검증·금지 표현 차단·폴백, 프로젝트·후보 저장, 좋아요/싫어요 취향 학습, 종합 랭킹 가중치(25/20/20/15/15/5).
- **사용자 결정 필요**: Windows 쪽 Ollama 설치 여부와 모델 / Claude Code·Antigravity CLI 실행 연동을 켤지(기본 꺼짐).

## Phase 5 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구(§7) | 구현 | 결과 성격 |
|---|---|---|
| 표준 발음·연음·받침-초성 결합 | 표준발음법 9개 규칙 엔진, 적용 규칙·위치 설명 | calculated |
| 반복음·리듬·빠르게 부르기 | 발음 특징 7종 + 발음 편의 루브릭 v0 | calculated / subjective |
| 부정적 연상 | 주의 단어 25개, 표기·발음 4형태 × 정확/유사음 매칭 | candidate (판정 아님) |
| 의미 | 한자 영어 풀이 + 주의 키워드. 한국어 뜻·조합 평가는 자료 없음 | candidate / not_available |
| 순우리말 어원 | 확인된 출처 없음 | not_applicable |
| 시간 경과(연령별) | 휴리스틱 참고 4종 | subjective |
| 국제 활용 | RR 로마자(인명 원칙), 성씨 관용 표기 예, 영어권 오해 철자 후보 | calculated / candidate |
| 중복·유사성 | 자모·음절·구조 결합 유사도, 중복 판정 | calculated |
| 금지 표현 | lint 규칙 + 프로젝트 전 문구 검사 | gate |
| API | `POST /names/analyze`, `POST /names/similarity` | |

### 완료 게이트: "명확한 판정/미확인 구분" — 충족
모든 분석 섹션이 `calculated / subjective / candidate / not_available / not_applicable` 중 하나를 명시(테스트 `test_every_section_has_explicit_status`). 부정 연상·뜻 주의는 '후보'로만, 근거 없는 한국어 뜻은 `not_available`.

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 5 신규: 발음 golden 20, 언어 분석 10, API 5) | 148 | 0 |

### 알려진 문제 / 메모
- 주의 단어·뜻 키워드는 소규모 개발자 목록 — 놓치는 표현이 있을 수 있음(화면에 명시).
- 한자의 한국어 뜻(훈)·의미 조합 평가는 국립국어원 자료 또는 Phase 7 AI 해설 후.
- 발음 미지원 규칙: ㄴ첨가, 사잇소리, 겹받침 세부.

### 다음 Phase(6) 준비 사항
- 생성/역검색: 규칙 기반 후보 생성(음절 조합·필터·발음 규칙), 한글→한자 조합 역검색·최적화, 대체 한자 추천, 강제 필터(검증 실패 제거·미확인 '보류'), 중복 제거·다양성. **이름 음절 사전**(이름에 쓰는 음절·조합)이 필요 — 공개 통계 자료 전에는 인명용 독음 플래그가 있는 한자 독음 + 개발자 큐레이션 음절 목록으로 진행.

## Phase 4 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| 원형이정 4격 | 단성·복성(합산)·외자(가수 옵션)·3자 이상 |
| 81수리 | 환원 규칙(calc) + 통용 길흉 분류(trad, 1~81, 학파 차이 12개 표시) |
| 획수 체계 | 현대 필획 / 성명학 원획(부수 본자 환원 규칙) 분리 저장 — 8,525자 원획 적재, 숫자 한자 뜻 계산 옵션 |
| 오행 | 수리오행(calc), 음령오행 2학파 + 일치도, 삼원오행·자원오행(부수 규칙)(trad), 상생·상극 관계 |
| 음양 | 홀짝 배열(calc) + 편중/조화(trad) |
| 학파 설정 | `stroke_system`, `single_name_virtual_stroke`, `eumryeong_school`, `numeral_by_meaning` |
| API | `POST /numerology/calculate`, `/hanja`·`/surnames` 응답에 원획 추가 |

### 완료 게이트: "외자·복성·필획/원획 테스트"
| 항목 | 결과 |
|---|---|
| 외자 (가수 없음/있음) | NUM-4GYEOK-003/004 통과 |
| 복성 (가상 획수 / 실제 南宮) | NUM-4GYEOK-002, NUM-REAL-003 통과 |
| 필획 vs 원획 | 沈 7/8 — NUM-REAL-001/002 통과, 저장 테이블 분리 |
| 한글 전용 이름 | 획수 항목 not_applicable, 음령만 적용 (NUM-NA-001) |
| 획수 모르는 한자 | 0으로 채우지 않고 `unknown` |
| 원획 규칙 점검 | 대표 40자(沈·鄭·權·蓮·慧 등)가 작명서 통용값과 일치 (개발 중 점검, 문헌 대조 아님) |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 4 신규: golden 19, API 5) | 113 | 0 |

### 알려진 문제 / 메모
- 81수리·삼원·자원오행은 모두 **전통 해석 · 출처 대조 전**. 점수화는 Phase 7(랭킹)에서.
- 사주 용신·격국(REQ-SJ-002, P1)은 학파 정의 문헌이 없어 미구현.
- 자원오행은 부수 규칙으로 배정 가능한 글자만 — 나머지 null(판정 보류).

### 다음 Phase(5) 준비 사항
- 언어·의미 평가: 발음(연음·받침-초성·반복음·리듬), 부정 연상 후보, 한자 의미 조합, 연령별 사용성. 국립국어원 자료 이용조건 확인 전에는 **규칙 기반 발음 분석 + 직접 작성한 소규모 주의 단어 목록**으로 진행.

## Phase 3 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| 달력 | 양력↔음력·윤달 (korean-lunar-calendar, 역변환 검증으로 존재하지 않는 윤달 차단) |
| 절기 | JPL DE421 발췌본 + Skyfield로 24절기 절입 시각 (`datasets/ephemeris/`, 1900–2050) |
| 연·월·일·시주 | 입춘·12절 기준 연·월주, JDN 일주, 오호둔·오서둔, 표면 오행 개수 |
| 시주 경계 / 자시 | 조자시·야자시 옵션, 결과에 가정 기록 |
| 시간대 | IANA tz — 1954–61 UTC+8:30, 1948–60·1987–88 일광절약시간 제거, 없는/중복 시각 처리 |
| 진태양시 | 지방평균시 / 진태양시(균시차 포함, 행성력 직접 계산) 옵션 |
| 범위 계산 | 4주 변화 지점에서 1초 정밀도로 분할, 시간 미정 = 하루 전체, 평균 없음 |
| API | `POST /saju/calculate`, `GET /calendar/solar-terms` |
| 문서 | `docs/KASI_VERIFICATION.md` (외부 대조 체크리스트) |

### 완료 게이트: "외부 기준값 Golden Tests 일치" — **미충족**
| 항목 | 결과 |
|---|---|
| Golden 23건 (`saju.yaml`) | 23 통과 — 모두 `formula_derived`, **externally_verified 0건** |
| 독립 구현 교차검증 | 일진: JDN 공식 ↔ 음력 라이브러리 무작위 300일 일치. 음력 왕복 변환 150일 일치 |
| 절기 시각 | 2024–2027 입춘이 널리 공개된 값(17:27, 23:10, 05:02, 10:46)과 일치하나 KASI 원문 대조 전 |
| 남은 작업 | 사용자가 KASI에서 `KASI_VERIFICATION.md` 11개 항목 확인 → `externally_verified` 로 갱신 |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 3 신규: golden 24, 속성 10, API 8) | 89 | 0 |
| vitest | 10 | 0 |
| Docker: 입춘 당일 범위 계산 | 정상 (10:46:19 연·월주 전환) | |

### Phase 0 초안 정정
- `SAJU-BOUND-UNKNOWN-TIME`: 시간 미정 시 12구간 → **13구간**(子시가 00–01시·23–24시로 갈리고 일주가 다름).
- `SAJU-RANGE-002`: 지방평균시 경계 09:32 → 09:32:06 (초 단위 확정).

### 알려진 문제 / 메모
- 사주 용신·격국 등 **전통 해석(trad)** 은 이 Phase 범위 아님 — Phase 4 이후 학파 프로필로 추가.
- 지장간 가중 오행(`include_hidden_stems: weighted`)은 미구현(옵션 off만).
- 지원 범위 1900–2050. 범위 밖은 `out_of_supported_range`.
- JPL 행성력 이용조건은 별도 라이선스 파일이 없어 NASA 일반 정책 근거로 기록 — 상용화 전 재확인 필요.

### 다음 Phase(4) 준비 사항
- 전통 성명학(원형이정·81수리·오행·학파): **81수리 길흉표와 원획 변환 기준 문헌 선택 필요**. 문헌 없이 가능한 범위(공식 정의 계산 13건 golden, 원획 변환 규칙 골격)는 먼저 구현 가능.

## Phase 2 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| DB schema | 마이그레이션 `0002` — hanja_characters / readings / variants / stroke_counts / element_mappings, official_name_character_rules, surnames / surname_variants, dictionary_terms, name_popularity_datasets / rows (11 테이블) |
| seed | Unihan 18.0.0 → 한자 8,525자 · 독음 8,917 · 현대 필획 8,525 · 이체자 5,930 (모두 `unverified`). 성씨 시드 120개(단성 112 + 복성 8) |
| import pipeline | `tasks.py fetch-unihan / import-data / import-official` — 체크섬·data_release_versions 기록, 재실행 멱등, 출처 manifest → reference_sources 동기화 |
| 조회 API | `GET /surnames`, `POST /surnames/provisional`, `GET /hanja`, `GET /hanja/{cp}`, `GET /admin/data` |
| UI | `/admin/data` — 데이터 현황·출처·데이터 버전, 공식 자료 미적재 경고 |
| 텍스트 정규화 | 호환 한자 보존(NFC 접기 금지), 한글 자모 합성 (D-013) |

### 완료 게이트: "이체자·독음·획수 출처 검증"
| 항목 | 결과 |
|---|---|
| 이체자 | 호환한자 ↔ 통합한자 링크(예: U+F9E1 李(이) → U+674E), 조회 시 계열 함께 반환, NFC로 접히지 않음 — **통과** |
| 독음 | 다중 독음(樂: 낙·락·악·요)과 플래그별 인명용 힌트 분리, 출처 `SRC-UNIHAN`·상태 `unverified` 필수 — **통과** |
| 획수 | 현대 필획만 적재(`STROKE.MODERN.UNIHAN.v1`), 원획 0건(Phase 4) — 필드·규칙 분리 **통과** |
| 성씨 교차검증 | 시드 120개 한자 독음을 Unihan과 자동 대조 → 충돌 0 |
| 공식 판정 분리 | 공식 미적재 시 `unknown` + 경고, 샘플은 `sample_only`, 실제 적재 시 `verified` / `not_listed` / 출처 충돌 시 `conflict` — 테스트로 검증 |
| **공식 인명용 한자표 적재** | **미완료** — 원본 파일·이용조건 미확보. 가져오기 경로(정규화 CSV)만 구현·테스트 |
| 어휘(dictionary_terms) | 스키마만. 국립국어원 자료 이용조건 확인 후 Phase 5에서 적재 |
| 이름 통계 | 스키마만. 공개 통계 수동 확인 후 적재 |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest 전체 (Phase 2 신규: 정규화 5, 가져오기 12, 조회 API 10) | 48 | 0 |
| vitest (신규: 데이터 관리 화면 1) | 10 | 0 |
| tsc / next build | 통과 | |
| 실제 기동: 전체 Unihan 적재 후 프록시 경유 조회(심 인명 한자 15자, 沈 계열 U+6C88·U+F972) | 정상 | |
| Docker compose: 컨테이너 기동 시 import-data → 조회 | 정상 | |

### 알려진 문제 / 메모
- 성씨 시드·Unihan 독음은 공식 근거가 아님 — 화면·API 모두 `unverified`로 표시.
- Unihan `kKoreanName`은 2015/2018판 기준이라 현행 인명용 한자표와 다를 수 있음.
- 개발 서버 종료: 세션 도구의 강제 종료로는 Windows 측 자식 프로세스에 신호가 전달되지 않아 수동 정리함. 터미널 Ctrl+C 경로의 트리 종료는 아직 직접 확인하지 못함.

### 다음 Phase(3) 준비 사항
- 만세력·사주 엔진: 음양력 변환, 절기(천문 계산), 사주 4주, 자시 옵션, 시간 범위 분할. **외부 기준값(KASI) 대조가 완료 게이트** — 조회 방법(웹 수동 조회 또는 사용자가 발급한 공공데이터 API 키) 결정 필요.

## Phase 1 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 | 구현 |
|---|---|
| Next.js | `apps/web` — Next 16.4 + React 19.3 + Tailwind v4 + shadcn/ui 방식 컴포넌트, §15 화면 19개 라우트(placeholder), 반응형 내비, PWA manifest, 라이트/다크 토큰 |
| FastAPI | `apps/api/namecraft_api` — 앱 팩토리, 공통 응답 envelope(REQ-NF-001), 구조화 오류, CORS 제한 |
| DB | SQLAlchemy 2 + Alembic, SQLite 기본. 마이그레이션 `0001`(users, audit_logs, reference_sources, data_release_versions) |
| Docker | `docker-compose.yml` + `docker/*.Dockerfile`, 127.0.0.1 바인딩 |
| CI 없는 로컬 테스트 명령 | `python scripts/tasks.py test` (pytest + vitest + tsc) |
| 기본 인증 | 로컬 단일 사용자 토큰 + Next 서버 프록시(토큰 브라우저 비노출, 교차 출처/CSRF 차단) |
| (§32) AI UI 라우트·Collector 뼈대 | `AIProvider`/`UsageCollector` 프로토콜, mock 3종, `/api/v1/ai/providers` (mock 표시), `/ai/providers` 화면 + 오류 UX(규칙 기반 폴백 안내·재시도) |
| 기타 | PII 로그 마스킹 필터, `.env.example`(유료 API 키 없음), `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` |

### 완료 게이트: "원클릭 로컬 기동 · API 헬스체크"
| 확인 | 결과 |
|---|---|
| `tasks.py dev` 실제 기동 → `GET /api/v1/health` | 200, `db: {ok: true, revision: "0001"}` |
| 토큰 없이 보호 API | 401 |
| 웹 프록시 경유 `/ai/providers` | 200, mock 3종 (ollama unknown / claude_code·antigravity disabled) |
| 프록시 교차 출처 요청 / CSRF 헤더 없는 POST | 403 / 403 |
| 웹 라우트 `/dashboard`, `/ai/providers`, `/projects/abc/recommendations`, `/admin/data` | 200 |
| `docker compose build` + `up` → health·프록시 | 성공 (동일 결과) |
| `next build` (프로덕션) | 성공, 경고 0 |

### 테스트 결과
| 묶음 | 통과 | 실패 |
|---|---:|---:|
| pytest (API 기반 6, AI mock 6, 보안 정책 5, 데이터셋 구조 4) | 21 | 0 |
| vitest (라우트 IA 2, 프록시 가드 4, Provider UI·배지 3) | 9 | 0 |
| tsc --noEmit | 통과 | |

Golden test의 **계산** 검증은 아직 없음(구조 검증만) — Phase 3·4 범위.

### 알려진 문제 / 메모
- 런타임은 Windows Python 3.14 + Windows Node 24(D-010). WSL에서 `uv` 설치가 자동 권한 정책으로 거부되어 기존 설치 도구를 사용함.
- Windows에서 `tasks.py dev` 종료 시 uvicorn reload 워커가 남는 문제 발견 → `taskkill /T`로 트리 종료하도록 수정(수정 후 재기동 검증은 미실시, 테스트 스위트는 재통과).
- `packages/contracts`·`packages/design-system`은 필요 시점까지 보류(ARCHITECTURE.md §2).

### 다음 Phase(2) 준비 사항
- 성씨·한자·어휘 DB 스키마/시드/import 파이프라인/조회 API. **공식 인명용 한자표 파일과 이용조건 확인이 필요**(DATA_SOURCES §4) — 확보 전에는 Unihan 기반 `unverified` 데이터와 소규모 sample로 파이프라인만 검증.

## Phase 0 — 완료 보고 (2026-11-19)

### 산출물
| 기획서 요구 산출물 | 파일 |
|---|---|
| REQUIREMENTS | `docs/REQUIREMENTS.md` (요구사항 ID ~90개, 우선순위·Phase 매핑) |
| 데이터 출처 목록 | `docs/DATA_SOURCES.md`, `datasets/source-manifests/*.yaml` (11개) |
| 계산 프로필 사양 | `docs/ANALYSIS_RULES.md` (기본 프로필 `kr-common-2026` 0.1.0-draft) |
| Golden Tests 초안 | `datasets/golden-tests/saju.yaml`, `numerology.yaml` |
| (§32) capability matrix | `docs/AI_CAPABILITY_MATRIX.md` |
| (§32) 사용량 지표 정의 | `docs/AI_CAPABILITY_MATRIX.md` §4 |
| (§32) 모의 사용량 샘플 | `datasets/fixtures/ai-usage-demo.json` (모든 레코드 `is_demo: true`) |
| 기타 | `docs/QA_TEST_PLAN.md`, `docs/DECISIONS.md`, `docs/PROJECT_PLAN.md`, `README.md` |

### 완료 게이트: "출처·라이선스·규칙 정의 검토"
- 규칙 정의: **초안 완료** (검토 필요)
- 출처 목록: **완료**, 라이선스: **미확인** — 모든 출처 `candidate/license_review`. 공식 원문 확인은 사람 검토 항목으로 남김(자동 수집 미실시).
- Capability matrix: 로컬 CLI `--help` 기준 판정 완료. 약관 최종 확인은 사용자 항목.

### Golden Test 현황
| 파일 | definitional | formula_derived | externally_verified | pending |
|---|---:|---:|---:|---:|
| saju.yaml | 0 | 6 | 0 | 4 |
| numerology.yaml | 13 | 0 | 0 | 1 |

(테스트 실행기는 Phase 1에서 구현 — 현재 실행된 테스트 없음)

### 알려진 문제 / 미결
- `docs/DECISIONS.md` Open Questions 1~6.
- formula_derived 사주 기대값은 KASI 등 외부 기준 대조 전이므로 Phase 3 완료 근거가 될 수 없음.

### 다음 Phase(1) 준비 사항
- 개발 도구 결정(Open Questions 1~3) 후 Monorepo 뼈대, FastAPI `/api/v1/health`, Next.js 기본 라우트(§15 전체 라우트 placeholder 포함 AI 라우트), DB(SQLite+Alembic), Provider/Collector 인터페이스 mock, `make test`.
