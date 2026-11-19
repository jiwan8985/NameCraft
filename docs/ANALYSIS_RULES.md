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
| SAJU.YEAR.v1 | calc | 연주 경계 = **입춘 절입 시각**. 연간지 idx = (year − 4) mod 60 (입춘 전이면 year−1) | — |
| SAJU.MONTH.v1 | calc | 월지 = 절 기준(寅월=입춘~경칩). 월간 = 오호둔(五虎遁): 甲己년→丙寅, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅 | — |
| SAJU.DAY.v1 | calc | 일진 idx = (JDN + 49) mod 60, 甲子=0. JDN은 **해당 지역의 일자 경계 기준** 날짜로 계산 | `day_boundary: midnight \| zi_hour_start` |
| SAJU.HOUR.v1 | calc | 시지: 子(23–01), 丑(01–03) … 2시간 단위. 시간 = 오서둔(五鼠遁): 甲己일→甲子, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子 | `zi_convention` 아래 |
| SAJU.ZI.v1 | calc | 자시 처리 | `zi_convention: jojasi_next_day`(23시부터 다음 날 일주, 기본) \| `yajasi_same_day`(23–24시는 당일 일주 + 다음 날 子시 천간) |
| SAJU.RANGE.v1 | calc | 시간 범위 입력 → [시주 경계, 절기 경계, 일자 경계, 자시 경계] 합집합으로 구간 분할 → 구간별 명식 + 가정 기록. **평균하지 않음** | — |
| SAJU.ELEMENTS.v1 | calc | 천간·지지 오행 기초 분포(지장간 미포함 기본) | `include_hidden_stems: false \| weighted` |
| SAJU.YONGSIN.* | trad | 억부·조후·통관·격국 등 학파별. 결과는 복수 의견으로 반환하며 이견 표시. "부족 오행 = 필수 보충" 규칙 사용 금지 | 학파별 플러그인 |

## 3. 획수 체계 (Phase 2·4)

| rule_id | 종류 | 정의 |
|---|---|---|
| STROKE.MODERN.UNIHAN.v1 | calc(데이터) | 현대 필획 = Unihan `kTotalStrokes`. 값이 2개면 UAX #38상 둘째(zh-Hant 선호)값 사용(한국 정자 기준). 상태 unverified (Phase 2 구현) |
| STROKE.ORIGINAL.v1 | trad | 성명학 원획(강희 기준 + 부수 본자 환원: 氵→水 4, 扌→手 4, 忄→心 4, 犭→犬 4, 礻→示 5, 衤→衣 6, 月(肉)→肉 6, 艹→艸 6, 辶→辵 7, 阝(左, 阜)→8, 阝(右, 邑)→7, 王(玉)→玉 5 등). **학파마다 다를 수 있어 표 전체를 프로필 데이터로 관리** |
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
- 81수리 길흉 `NUM.LUCK81.*` (**trad**): 학파·문헌별 표를 데이터로 주입. Phase 0에서는 표를 포함하지 않는다.
- 음양 배합 `NUM.YINYANG.v1` (calc+trad): 각 글자 획수 홀=양, 짝=음. 배열 패턴 계산은 calc, 길흉 판정은 trad.
- 수리오행 `NUM.ELEMENT.v1` (calc): 끝자리 1·2 木, 3·4 火, 5·6 土, 7·8 金, 9·0 水.
- 삼원오행 `NUM.SAMWON.*` (trad): 학파별 정의 상이 → Phase 4에서 문헌 확정 후 등록.
- 자원오행 `NUM.JAWON.*` (trad): 한자별 학파 매핑 데이터(`hanja_element_mappings`), 출처 필수.

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

## 5. 평가·랭킹 (Phase 7)

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

## 6. 기본 프로필 (초안)

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
