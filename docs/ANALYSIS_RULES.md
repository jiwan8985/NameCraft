# 분석 규칙·계산 프로필 사양 (ANALYSIS_RULES)

> 기획서 §6, §10 기준. Phase 0 산출물(사양 초안). 실제 공식의 확정은 해당 Phase(3·4)에서 Golden Test 통과 후 `rule_version`을 `1.0.0`으로 올린다.
> **원칙:** 결정론적 계산(`calc`)과 전통 해석(`trad`)을 다른 함수·다른 결과 필드로 분리한다. 해석은 미래를 보증하지 않는다.

## 1. 프로필 구조

모든 규칙은 아래 스키마로 관리한다(REQ-NUM-004).

```yaml
profile_id: kr-common-2026          # 학파/설정 묶음 ID
rule_version: 0.1.0-draft           # SemVer, 결과에 함께 저장
description: "현대 한국 작명 통용 기준(초안)"
rules:
  - rule_id: NUM.WONHYEONG.v1
    kind: calc                        # calc | trad
    formula: "..."                    # 사람이 읽는 수식
    params: {...}                     # 프로필별 옵션
    citation: SRC-NUM-TRAD#...        # 근거(없으면 null + warning)
    test_cases: golden-tests/numerology.yaml#...
```

결과에는 항상 `profile_id`, `rule_version`, 적용 `rule_id` 목록, `calculation_assumptions`를 기록한다.

## 2. 달력·만세력 (Phase 3)

| rule_id | 종류 | 정의 | 프로필 옵션 |
|---|---|---|---|
| CAL.TZ.v1 | calc | 입력 지역 시각 → UTC. 한국의 **역사적 표준시 변경**(1954–1961 UTC+8:30 등)과 **일광절약시간**(1948–1960, 1987–1988)을 tz database(`Asia/Seoul`)로 반영 | `tz_source: iana` |
| CAL.SOLARTIME.v1 | calc | 진태양시 = 표준시 + (경도 − 표준자오선)×4분 (+ 균시차 선택) | `true_solar_time: off \| longitude_only \| with_equation_of_time` (기본 off) |
| CAL.LUNAR.v1 | calc | 양력↔음력·윤달 변환. KASI 기준값과 Golden Test 일치 필수 | — |
| CAL.SOLARTERM.v1 | calc | 절기 = 태양 시황경 15°×k 통과 시각(천문 계산). 월주 경계는 12절(입춘·경칩·청명·입하·망종·소서·입추·백로·한로·입동·대설·소한) | `ephemeris: de421` |
| SAJU.YEAR.v1 | calc | 연주 경계 = **입춘 절입 시각**. 연간지 idx = (year − 4) mod 60. 구현: 월주와 같은 태양 황경 구간에서 유도(子·丑월이면서 1·2월이면 전년) — 연·월주 경계가 항상 같은 순간 | — |
| SAJU.MONTH.v1 | calc | 월지 = 절 기준(寅월=입춘~경칩). 월간 = 오호둔(五虎遁): 甲己년→丙寅, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅 | — |
| SAJU.DAY.v1 | calc | 일진 idx = (JDN + 49) mod 60, 甲子=0. JDN은 **해당 지역의 일자 경계 기준** 날짜로 계산 | `day_boundary: midnight \| zi_hour_start` |
| SAJU.HOUR.v1 | calc | 시지: 子(23–01), 丑(01–03) … 2시간 단위. 시간 = 오서둔(五鼠遁): 甲己일→甲子, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子 | `zi_convention` 아래 |
| SAJU.ZI.v1 | calc | 자시 처리 | `zi_convention: jojasi_next_day`(23시부터 다음 날 일주, 기본) \| `yajasi_same_day`(23–24시는 당일 일주 + 다음 날 子시 천간) |
| SAJU.RANGE.v1 | calc | 시간 범위 입력 → 4주 중 하나라도 바뀌는 지점에서 구간 분할(10분 간격 탐색 + 이분 탐색, 1초 정밀도). 경계 시각은 새 기둥이 처음 적용되는 **정수 초**로 보고 → 구간별 명식 + 변경된 기둥 + 가정 기록. **평균하지 않음**. 시간 미정 = 하루 전체(자시가 00–01·23–24로 갈려 13구간). 최대 62일 | — |
| SAJU.ELEMENTS.v1 | calc | 천간·지지 오행 기초 분포(지장간 미포함 기본) | `include_hidden_stems: false \| weighted` |
| SAJU.YONGSIN.* | trad | 억부·조후·통관·격국 등 학파별. 결과는 복수 의견으로 반환하며 이견 표시. "부족 오행 = 필수 보충" 규칙 사용 금지 | 학파별 플러그인 |

### 시각 기준 (Phase 3 구현)

| `true_solar_time` | 일주·시주에 쓰는 유효 지방시 |
|---|---|
| `off`(기본) | 해당 시간대의 **표준시** — 일광절약시간(1948–60, 1987–88) 제거, 역사적 표준시(1954–61 UTC+8:30) 반영. IANA tz database 기준 |
| `longitude_only` | 지방평균시 = UTC + 경도/15h |
| `with_equation_of_time` | 진태양시 = 태양 시간각 + 12h (JPL 행성력 직접 계산, 균시차 포함) |

- 연주·월주는 절입 **순간**과 비교하므로 시각 기준 옵션의 영향을 받지 않는다.
- 일광절약시간 시작으로 **존재하지 않는 시각**은 오류, 종료로 **두 번 존재하는 시각**은 앞의 시각으로 계산하고 경고.
- 지원 범위: 1900-01-01 ~ 2050-12-31 (행성력 발췌본·음력 라이브러리 범위).

## 3. 획수 체계 (Phase 2·4)

| rule_id | 종류 | 정의 |
|---|---|---|
| STROKE.MODERN.UNIHAN.v1 | calc(데이터) | 현대 필획 = Unihan `kTotalStrokes`. 값이 2개면 UAX #38상 둘째(zh-Hant 선호)값 사용(한국 정자 기준). 상태 unverified (Phase 2 구현) |
| STROKE.ORIGINAL.v1 | trad | 성명학 원획 = 강희 214부수 본래 획수 + Unihan `kRSUnicode` 나머지 획수 → 변형 부수(氵→水 4, 扌→手 4, 忄→心 4, 犭→犬 4, 礻→示 5, 衤→衣 6, 月(肉)→肉 6, 艹→艸 6, 辶→辵 7, 阝(左)→阜 8, 阝(右)→邑 7, 王→玉 5, 罒→网 6, 耂→老 6) 자동 환원. 간체/변형 부수 표기(') 는 미적용(unknown). 학파 예외는 profile 예외 표로 덮어씀(현재 없음). Phase 4 구현·8,525자 적재 |
| STROKE.NUMERAL.v1 | trad | 숫자 한자 획수 특례(一~十을 수의 뜻으로 1~10 적용하는 학파 존재) — 옵션 `numeral_by_meaning: false` 기본 |

필획과 원획은 **다른 테이블/필드**에 저장하고 계산 시 프로필의 `stroke_system: modern | original`을 명시한다.

## 4. 수리성명학 (Phase 4)

기호: 성 획수 `S`(복성은 `S = s1 + s2`), 이름 글자 획수 `n1, n2, …, nk`.

| rule_id | 종류 | 2자 이름 (k=2) | 외자 (k=1) | 3자 이상 |
|---|---|---|---|---|
| NUM.WON.v1 원격 | calc | n1 + n2 | n1 (+ 가수 옵션) | Σn |
| NUM.HYEONG.v1 형격 | calc | S + n1 | S + n1 | S + n1 |
| NUM.I.v1 이격 | calc | S + n2 | S (+ 가수 옵션) | S + Σn[2..k] |
| NUM.JEONG.v1 정격 | calc | S + n1 + n2 | S + n1 | S + Σn |

- 옵션 `single_name_virtual_stroke: none | plus_one` (외자 가수 1 적용 여부, 기본 `none`), `compound_surname_mode: sum`.
- 81수리 환원 `NUM.REDUCE81.v1`: n > 81이면 n − 80을 반복(옵션 `reduce: subtract_80`).
- 81수리 길흉 `NUM.LUCK81.KR-COMMON.v1` (**trad**, 출처 대조 전): `datasets/rules/luck81-kr-common.yaml` — 1~81 길/반길/흉 분류만 저장(문헌 해설 미전재). 학파 간 분류가 갈리는 12개 수(26·27·28·30·38·51·58·71·73·75·77·78)는 `disputed` + 대안 분류.
- 음양 배합 `NUM.YINYANG.v1` (calc+trad): 각 글자 획수 홀=양, 짝=음. 배열 패턴 계산은 calc, 판단(trad)은 '한쪽으로만 이루어지면 편중'만 표시.
- 수리오행 `NUM.ELEMENT.v1` (calc): 끝자리 1·2 木, 3·4 火, 5·6 土, 7·8 金, 9·0 水.
- 삼원오행 `NUM.SAMWON.KR-COMMON.v1` (trad, 출처 대조 전): 천격=성+1(복성은 성 합), 인격=성+이름 첫자, 지격=이름 합(외자 +1), 각 끝자리 수리오행 + 상생·상극 관계.
- 자원오행 `NUM.JAWON.RADICAL.v1` (trad, 출처 대조 전): 부수 의미가 오행과 직접 대응하는 경우만 배정(水·冫·雨→水, 木·艸·竹·禾→木, 火→火, 土·山·田→土, 金·玉·石→金), 그 외 판정 보류(null). 학파 매핑 표가 생기면 `hanja_element_mappings`로 덮어씀.

### 음령(발음)오행 `NUM.EUMRYEONG.*` (trad)

| 초성 | `hunmin-haerye` (훈민정음 해례본) | `modern-common` (현대 통용) |
|---|---|---|
| ㄱ ㅋ | 木 | 木 |
| ㄴ ㄷ ㄹ ㅌ | 火 | 火 |
| ㅇ ㅎ | **水** | **土** |
| ㅅ ㅈ ㅊ | 金 | 金 |
| ㅁ ㅂ ㅍ | **土** | **水** |

두 학파가 실제로 다르므로 프로필 옵션 `eumryeong_school`로 선택하고 학파 간 일치도(REQ-NUM-005)의 대표 사례로 사용한다.

### 적용 불가 처리
- 한글 전용/순우리말 이름: 한자 기반 규칙(획수·자원오행·수리) → `not_applicable`. 음령오행·발음 분석은 적용.
- 획수 데이터가 `unverified`인 글자: 계산은 하되 결과 `verification_status: unverified` + warning.

## 5. 언어·의미 (Phase 5)

| rule_id | 성격 | 정의 |
|---|---|---|
| PRON.* | calculated | 표준발음법 주요 규칙: 연음(LINK), 구개음화(PALATAL), ㅎ탈락(H_DROP), 거센소리되기(ASPIRATE), 받침 대표음(CODA), 비음화(NASAL), 유음화(LIQUID), 된소리되기(TENSE), 자음 뒤 ㅢ→ㅣ(UI). 미지원: ㄴ첨가·사잇소리·겹받침 세부 |
| LANG.PHONETIC.RUBRIC.v0 | subjective | 발음 편의 점수 = 100 − 감점. 표기≠발음 5, 된/거센소리 음절당 3, 받침+자음 충돌당 4, 모음 충돌당 3, 같은 음절 반복 6, 같은 초성 연속당 2 |
| LANG.CAUTION.KO.v1 | candidate | `datasets/rules/caution-words-ko.yaml` 대조. 이름·전체 이름의 표기·발음형 4가지 검사, 된/거센소리를 예사소리로 바꾼 '유사음' 매칭, `whole` 단어는 이름 전체 일치만. 결과는 검토 권장 후보 |
| LANG.MEANING.CAUTION.EN.v1 | candidate | Unihan 영어 풀이에 주의 키워드(단어 경계). 한국어 훈·의미 조합은 `not_available` |
| (휴리스틱) | subjective | 연령별 참고: 귀여운 음절, 같은 음절 반복, 3자 이상, 외자 |
| RR | calculated | 국어의 로마자 표기법(인명, 음운 변화 미반영, 모음 시작 음절 앞 붙임표). 성씨 관용 표기 예시·영어권 오해 철자 후보 병기 |
| LANG.SIMILARITY.v1 | calculated | 결합 = 0.45×자모 유사(발음형) + 0.35×음절 겹침(Jaccard) + 0.2×구조(음절 수·받침 패턴). 중복 = 한글 같고 (한자 같거나 둘 다 없음) |
| LANG.FORBIDDEN_CLAIMS.v1 | gate | `datasets/rules/forbidden-claims.yaml` — 보장·단정·운명 결정 표현 차단. 프로젝트 전체 문구를 테스트로 검사 |

## 6. 평가·랭킹 (Phase 7)

| 항목 | 기본 가중치 | 성격 |
|---|---:|---|
| 발음·어감 | 25 | calc + subj |
| 이름 의미 | 20 | fact + subj |
| 전통 사주·오행 해석 | 20 | trad |
| 전통 획수·수리 해석 | 15 | trad |
| 현대적 사용성 | 15 | subj |
| 희소성·개인 선호 | 5 | fact(공개 범위) + subj |

- `weights_normalized = w / Σw` (w ≥ 0, Σw > 0). 항목이 `N/A`면 제외 후 재정규화 + `incomplete_data` 경고.
- 유효성 게이트(`pass/fail/unknown`): 인명용 한자 허용, 하드 조건, 독음 가능성 — **점수와 분리**.
- 루브릭 상세는 Phase 5·7에서 본 문서에 추가.

## 7. 기본 프로필 (초안)

```yaml
profile_id: kr-common-2026
rule_version: 0.1.0-draft
options:
  tz_source: iana
  true_solar_time: off
  zi_convention: jojasi_next_day
  day_boundary: midnight
  include_hidden_stems: false
  stroke_system: original
  numeral_by_meaning: false
  single_name_virtual_stroke: none
  compound_surname_mode: sum
  reduce: subtract_80
  eumryeong_school: modern-common
status: draft   # Golden Test 통과 전까지 결과에 'draft profile' 경고
```
