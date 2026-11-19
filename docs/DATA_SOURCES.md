# 데이터 출처·라이선스 목록 (DATA_SOURCES)

> 기획서 §5, §26 기준. Phase 0 산출물. 기계 판독용 상세는 `datasets/source-manifests/*.yaml`.
> **상태 정의:** `candidate`(후보, 미검토) → `license_review`(이용조건 검토 중) → `approved`(수집 허용 확인) → `ingested`(수집·체크섬 기록) / `rejected`.
> Phase 0 시점 모든 출처는 **`candidate` 또는 `license_review`**이며, 이용 조건을 사람이 원문으로 확인하기 전에는 자동 수집하지 않는다(REQ-HJ-004).

## 1. 출처 목록

| ID | 출처 | 용도 | 권위 | 접근 방식(예정) | 라이선스/이용조건 | 상태 |
|---|---|---|---|---|---|---|
| SRC-SCOURT-HANJA | 대법원 전자가족관계등록시스템 — 인명용 한자표 | 인명용 한자 허용 여부·허용 독음 | **공식(법적 기준)** | 게시판 공개 첨부파일 수동 다운로드 → 체크섬 기록 → 파서 | 공공저작물 여부·재배포 범위 확인 필요 | license_review |
| SRC-LAW-FAMREG | 국가법령정보센터 — 「가족관계의 등록 등에 관한 규칙」 제37조 및 별표 | 인명용 한자 법적 근거·시행일 | **공식(법령)** | 수동 확인, 조문 번호·시행일만 기록 | 법령은 저작권 보호 대상 아님(저작권법 §7) — 재확인 | candidate |
| SRC-SCOURT-STATS | 대법원 전자가족관계등록 — 출생신고 이름 통계 | 이름 인기도(공개 상위 범위) | 공식(통계) | 화면 확인 후 수동 기록, 집계 기준 저장 | 재이용 조건 확인 필요 | candidate |
| SRC-KASI-LUNAR | 한국천문연구원(KASI) 음양력 정보 / 공공데이터포털 API | 양력↔음력·윤달 Golden Test 기준값 | 공식(천문) | 공공데이터포털 오픈API(인증키는 **사용자 개인 발급**, 앱 필수 아님) 또는 KASI 웹 수동 조회 | 공공누리 유형 확인 필요 | candidate |
| SRC-KASI-TERMS | KASI 24절기 절입 시각 | 절기 경계 Golden Test | 공식(천문) | 동일 | 동일 | candidate |
| SRC-JPL-DE | NASA JPL 행성력(DE421/DE440) + Skyfield | 절기(태양 황경 15° 배수) 독립 계산·교차검증 | 과학 기준 | 로컬 파일 다운로드 | JPL 공개 데이터(미 연방 저작물), Skyfield MIT | candidate |
| SRC-UNIHAN | Unicode Unihan Database | 코드포인트, 총획(`kTotalStrokes`), 부수-획(`kRSUnicode`), 한국 독음(`kHangul`), 호환한자 매핑 | 표준(Unicode) — **법적 기준 아님** | 공식 zip 다운로드, 버전 고정 | Unicode License v3 (허용적) | candidate |
| SRC-KRDICT | 국립국어원 한국어기초사전 | 어휘 의미·발음·동음이의어 | 공식(국어) | 오픈 API 또는 공개 데이터 | CC BY-SA 2.0 KR로 알려져 있음 — 원문 확인 필요 | license_review |
| SRC-STDICT | 국립국어원 표준국어대사전 | 표준 발음·어휘 의미 보완 | 공식(국어) | 오픈 API | 이용약관 확인 필요 | candidate |
| SRC-KLC-LIB | `korean-lunar-calendar` (Python) | 음양력 변환 구현 후보 | 비공식(구현체) | PyPI | MIT — 확인 필요 | candidate |
| SRC-NUM-TRAD | 수리성명학 81수리 길흉표, 원획 변환 규칙(부수 본자 환원) | 전통 해석 규칙 | **전통 해석(학파별)** | 문헌 수동 정리, 학파·서지 기록 | 저작물 인용 범위 확인 필요 — 표 자체 전재 금지, 규칙 요약만 | candidate |

## 2. 권위 순위 (충돌 시)

1. 인명용 한자 허용/독음: `SRC-SCOURT-HANJA` + `SRC-LAW-FAMREG` **만** `verified` 근거가 될 수 있다. Unihan·사전·작명 문헌의 독음은 `unverified` 보조 정보.
2. 음양력/절기: `SRC-KASI-*` 우선, `SRC-JPL-DE` 독립 계산으로 교차검증. 구현 라이브러리 출력은 Golden Test 통과 시에만 채택.
3. 획수: 현대 필획은 Unihan `kTotalStrokes`를 **초기값(unverified)** 으로 쓰고, 성명학 원획은 학파 프로필의 변환 규칙으로 별도 산출한다(같은 필드 공유 금지, REQ-NUM-002).
4. 의미/발음: 국립국어원 자료 우선. AI 생성 설명은 `subjective`.

## 3. 수집 운영 규칙 (기획서 §26 운영 정책)

- 원천(raw)과 가공본(processed)을 분리 저장: `datasets/raw/<SRC-ID>/<retrieved_at>/` (Git 미포함, 체크섬만 manifest에 기록).
- manifest 필수 필드: `id, name, url, authority, purpose, access_method, license, license_verified_at, terms_url, retrieved_at, effective_date, checksum_sha256, coverage, status, notes`.
- 갱신 실패·형식 변경은 `data_release_versions`와 감사 로그에 기록.
- 신뢰할 수 없는 자료는 출생신고 적합성 판정에 사용 금지.
- 스크래핑은 이용조건이 명시적으로 허용하고, robots·요청 빈도 제한을 지킬 때만. 기본은 **수동 다운로드 + 체크섬**.

## 4. 사용자 확인이 필요한 항목

- [ ] 대법원 인명용 한자표 첨부파일의 재배포/가공 허용 여부 (공공누리 유형 표기 확인)
- [ ] 한국어기초사전 API 이용약관 및 출처표시 방식
- [ ] KASI/공공데이터포털 API 사용 여부 (사용 시 사용자가 직접 인증키 발급 — 앱은 키 없이도 동작해야 함)
- [ ] 81수리 해석에 사용할 기준 문헌/학파 선택 (최소 1개 기본 프로필)
