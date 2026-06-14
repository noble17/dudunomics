# 후보 발굴 Candidate Screener 설계

## 배경

현재 Dudunomics는 관심종목, 보유종목, S&P500, NASDAQ100, KOSPI200, KOSDAQ150 중심으로 가격, 펀더멘털, 성장 점수, 타이밍 점수를 관리한다. 이 구조는 이미 알려진 대표 종목을 안정적으로 분석하기 좋지만, LITE처럼 S&P500/NASDAQ100 편입 전에 강하게 올라오는 중대형 성장주를 조기에 발견하기에는 유니버스가 좁다.

이번 기능의 목표는 관심종목에 이미 들어간 종목을 분석하는 데서 한 단계 더 나아가, 아직 관심종목에 없는 후보를 넓은 유니버스에서 찾아내는 것이다.

## 목표

- Russell 1000, NASDAQ100, S&P500, KOSPI, KOSDAQ 후보군을 비교한다.
- 겹치는 종목은 자동으로 제거한다.
- 미국 후보는 기본적으로 기술주 중심으로 비교하되, 섹터 필터를 선택할 수 있게 한다.
- 국장은 KOSPI/KOSDAQ을 나누어 최종 후보를 만든다.
- 최종 후보는 미국 30개, 국장 20개, 총 50개를 목표로 한다.
- 사용자는 후보 중 관심종목에 넣을 종목을 직접 선택한다.
- 후보 판별 조건은 UI에서 켜고 끌 수 있어야 한다.
- 전체 유니버스에 과도한 상세 수집을 하지 않는다.

## 완료 정의

v1 완료는 다음 조건으로 판단한다.

- `russell1000` 유니버스가 추가되어 월 1회 티커 캐시를 갱신한다.
- 후보 발굴 배치가 미국/국장 후보 pool을 만들고 dedupe한다.
- 후보 점수 결과가 DB에 저장된다.
- 후보 발굴 화면에서 미국 Top30, 국장 Top20을 볼 수 있다.
- 사용자는 섹터, 성장, 밸류, 수익성, 타이밍 조건을 선택/제외할 수 있다.
- 이미 관심종목에 있는 종목은 표시하거나 제외하는 옵션을 제공한다.
- 후보 row에서 관심종목 추가가 가능하다.
- ChoiceStock 공개 HTML 수집은 전체 후보군이나 최종 후보 상태에는 적용하지 않고, 사용자가 관심종목으로 추가한 뒤에만 적용한다.

## 후보 상태와 제외 정책

후보 발굴의 기본 목적은 "아직 사용자가 판단하지 않은 새 후보"를 찾는 것이다. 따라서 이미 사용자가 액션한 종목은 기본 결과에서 제외하고, 필요할 때만 필터를 풀어 다시 볼 수 있게 한다.

후보 상태는 다음처럼 구분한다.

```text
new
아직 사용자가 판단하지 않은 신규 후보.

watching
사용자가 최종 후보 또는 검토 중으로 표시한 종목.

added
사용자가 관심종목에 추가한 종목.

dismissed
사용자가 후보에서 제외한 종목.
```

기본 필터 동작:

- 관심종목에 이미 있는 종목은 기본 결과에서 제외한다.
- `watching` 상태의 종목은 기본 결과에서 제외하고 "검토 중" 탭에서 보여준다.
- `added` 상태의 종목은 기본 결과에서 제외하고 "관심종목 편입" 탭에서 보여준다.
- `dismissed` 상태의 종목은 기본 결과에서 숨긴다.
- 사용자가 필터를 끄면 위 상태의 종목도 다시 볼 수 있다.

UI 탭:

- 신규 후보
- 검토 중
- 관심종목 편입
- 제외됨

기본 토글:

- `관심종목 제외`: ON
- `검토 중 제외`: ON
- `제외한 종목 숨김`: ON

이 정책은 매일 후보 Top10/Top30이 반복적으로 같은 종목만 보여주는 문제를 줄이기 위한 것이다.

## 유니버스 정책

### 미국

미국 후보 pool은 다음 합집합이다.

- Russell 1000
- NASDAQ100
- S&P500

dedupe 기준은 ticker다.

기본 필터는 기술주 중심이다.

- 기본: `Technology`, `Communication Services` 중 AI/반도체/소프트웨어 관련 산업
- 옵션: 전체 섹터, 반도체, 소프트웨어, AI 인프라, 커뮤니케이션 장비, 데이터센터

NASDAQ100과 S&P500은 이미 대표 대형주 중심이므로, 조기 발굴은 Russell 1000이 담당한다. Russell 1000은 LITE 같은 S&P/Nasdaq100 편입 전 중대형 성장주를 포착하기 위한 핵심 확장 유니버스다.

### 국장

국장 후보 pool은 다음과 같다.

- KOSPI
- KOSDAQ

다만 전체 상장사를 그대로 상세 분석하지 않는다. v1에서는 데이터 안정성을 위해 다음 필터를 먼저 적용한다.

- 시가총액 하한
- 거래대금 또는 거래량 하한
- 가격/OHLCV 수집 가능 여부
- 관리종목/거래정지 등 위험 상태 제외 가능

최종 후보는 KOSPI Top10, KOSDAQ Top10을 기본으로 한다.

## 데이터 수집 원칙

후보 발굴은 넓은 universe를 다루므로 데이터 계층을 두 단계로 나눈다.

### 1차 전체 수집

전체 후보군에는 가벼운 데이터만 수집한다.

- 티커
- 회사명
- 시장/거래소
- 섹터/산업
- 시가총액
- 가격/OHLCV
- 거래량/거래대금
- 1M/3M/6M/YTD 모멘텀
- 52주 고점 대비 위치
- 기본 valuation: Forward PER, PEG, PSR 가능 범위
- 기본 quality/growth: ROE, 매출 성장률, EPS 성장률 가능 범위
- 기술지표: RSI, EMA20/50/200, MA200 위 여부

### 2차 상세 수집

상세 수집은 사용자가 후보를 관심종목으로 추가한 뒤에만 실행한다. 최종 후보 또는 `watching` 상태는 아직 사용자의 관심종목 선택이 확정된 상태가 아니므로 ChoiceStock 수집 대상이 아니다.

- 뉴스 링크
- 연간 매출/EPS/ROE 차트 데이터
- 목표주가 consensus
- 상세 valuation/timing 설명

ChoiceStock 공개 데이터는 관심종목 편입 후 `choicestock_public_hydrate` 작업이 하루 1회 캐시한다. Russell 1000 전체, 최종 후보 Top50, `watching` 상태 종목에는 ChoiceStock을 적용하지 않는다.

## 데이터 Source

### 티커 목록

미국:

- Russell 1000: iShares IWB holdings CSV 또는 FTSE Russell 공개 자료
- S&P500: Wikipedia 공개 표 또는 기존 JSON cache
- NASDAQ100: Nasdaq/공개 표 또는 기존 JSON cache

국장:

- KOSPI/KOSDAQ: FinanceDataReader KRX listing 또는 KRX 공개 데이터

### 가격/OHLCV

- 기본: 기존 `fetch_ohlcv`/Toss 우선 정책을 따른다.
- 화면 조회는 DB/cache만 읽는다.
- 후보 배치와 명시 보강만 외부 호출을 수행한다.

### 기본 펀더멘털

미국:

- 기존 `fundamentals_extended`
- Finviz bulk
- StockAnalysis 가능한 범위
- FMP는 요금제/한도 제한 때문에 기본 후보 전체 수집에는 사용하지 않는다.

국장:

- Naver Finance
- OpenDART
- 기존 quarterly/quant score 경로

### ChoiceStock

- 전체 후보군 수집에는 사용하지 않는다.
- 최종 후보 또는 `watching` 상태에는 사용하지 않는다.
- 관심종목 편입 후 하루 1회 캐시에만 사용한다.

## 후보 점수

후보 점수는 계산 결과이며 원천 데이터와 분리한다.

기본 composite:

```text
candidate_score =
  growth_score * w_growth
  + quality_score * w_quality
  + valuation_score * w_valuation
  + momentum_score * w_momentum
  + timing_score * w_timing
  + liquidity_score * w_liquidity
```

기본 가중치:

```text
growth      25%
quality     20%
valuation   15%
momentum    20%
timing      15%
liquidity    5%
```

UI에서 preset을 제공한다.

- 균형형
- 성장 우선
- 밸류 우선
- 타이밍 우선
- 눌림 대기형

## 필터 옵션

후보 발굴 화면에서 사용자가 선택할 수 있는 조건:

- 국가/시장: 미국, 국장, 전체
- 미국 universe: Russell 1000, S&P500, NASDAQ100, 전체
- 국장 universe: KOSPI, KOSDAQ, 전체
- 섹터: 기술주만, 전체 섹터, 반도체, 소프트웨어, AI 인프라 등
- 관심종목 제외: 켜기/끄기
- 최소 시가총액
- 최소 거래대금
- RSI 70 이상 제외
- MA200 위 종목만
- EMA 정배열만
- EMA20/50 눌림 포함
- Forward PER 상한
- PEG 상한
- ROE 하한
- EPS 성장률 양수만
- 매출 성장률 양수만

필터는 서버에서 저장된 후보 snapshot에 적용한다. 필터 변경만으로 외부 데이터를 다시 수집하지 않는다.

## DB 설계

### `candidate_universe_members`

유니버스별 멤버십을 저장한다.

- `universe`
- `ticker`
- `name`
- `market`
- `sector`
- `industry`
- `source`
- `as_of`
- `fetched_at`
- primary key: `(universe, ticker, as_of)`

### `candidate_scores`

후보 발굴 점수 결과를 저장한다.

- `as_of`
- `region`: `US` 또는 `KR`
- `universe_group`: `us_growth`, `kospi`, `kosdaq` 등
- `ticker`
- `name`
- `market`
- `sector`
- `industry`
- `candidate_score`
- `growth_score`
- `quality_score`
- `valuation_score`
- `momentum_score`
- `timing_score`
- `liquidity_score`
- `rank`
- `raw_json`
- `created_at`
- primary key: `(as_of, region, universe_group, ticker)`

### `candidate_shortlist`

사용자별 후보 검토 상태를 저장한다.

- `user_id`
- `as_of`
- `ticker`
- `universe_group`
- `status`: `new`, `watching`, `dismissed`, `added`
- `memo`
- `updated_at`
- primary key: `(user_id, as_of, ticker, universe_group)`

## 배치 설계

### `candidate_universe_refresh`

주기: 매월 1일 06:20 KST의 `universe_tickers_refresh` 이후.

역할:

- Russell 1000, S&P500, NASDAQ100, KOSPI, KOSDAQ 티커 목록 갱신
- 유니버스 멤버십 DB 저장
- 겹치는 ticker는 멤버십에는 모두 저장하되 후보 pool 계산 시 dedupe

### `candidate_score_us`

주기: 매일 07:30 KST.

역할:

- 미국 후보 pool dedupe
- 가격/OHLCV, 기본 펀더멘털, 섹터/산업, 유동성 데이터 수집
- 기본 필터 적용
- 기술주 옵션 기준 점수 계산
- 미국 Top30 저장

### `candidate_score_kr`

주기: 매일 16:30 KST.

역할:

- KOSPI/KOSDAQ 후보 pool 생성
- 가격/OHLCV, Naver/OpenDART, 유동성 데이터 수집
- KOSPI Top10, KOSDAQ Top10 저장

### `candidate_daily_digest`

주기: 매일 08:55 KST 또는 사용자가 켠 경우.

역할:

- 새 후보/순위 상승 후보 요약
- 관심종목에 없는 후보만 발송 가능
- Telegram `daily` 또는 별도 후보 채널 사용 가능

## API 설계

### `GET /api/candidates`

쿼리:

- `region`
- `universe_group`
- `sector`
- `exclude_watchlist`
- `preset`
- `limit`
- `filters`

응답:

- 후보 row 목록
- 점수 breakdown
- 데이터 기준일
- 적용 필터

### `POST /api/candidates/refresh`

수동 후보 배치 실행.

### `PUT /api/candidates/{ticker}/shortlist`

후보 상태 변경.

- `watching`
- `dismissed`
- `added`

### `POST /api/candidates/{ticker}/add-watchlist`

관심종목 추가.

## UI 설계

신규 화면: `/candidates`

상단:

- 미국/국장 segmented control
- preset 선택
- 섹터 선택
- 관심종목 제외 토글
- 최소 시총/거래대금 필터

본문:

- 미국 Top30
- KOSPI Top10
- KOSDAQ Top10
- 점수 breakdown column
- 타이밍 badge
- 관심종목 추가 버튼
- 제외 버튼

상세:

- 선택 ticker sticky header
- 가격/EMA 차트
- valuation/timing 요약
- 데이터 상태
- 관심종목 추가 후 ChoiceStock 상세 보강 안내

## 리스크와 제한

- Russell 1000 전체에 상세 HTML 수집을 하면 요청 수가 과도하다.
- 섹터/산업 분류 source가 서로 다를 수 있어 normalized sector mapping이 필요하다.
- 미국과 국장은 데이터 availability가 달라 같은 점수식을 그대로 쓰면 왜곡될 수 있다.
- 작은 종목으로 universe를 너무 넓히면 데이터 품질과 잡음이 급격히 나빠진다.
- 점수는 매수 추천이 아니라 후보 압축 도구로 표시해야 한다.

## 구현 순서

1. Russell 1000 ticker provider 추가.
2. 유니버스 멤버십 DB 저장.
3. 후보 점수 DB 테이블 추가.
4. 기존 `quant_scores`/`growth_score`를 재사용한 후보 스코어링 v1 작성.
5. `/api/candidates` 조회 API 작성.
6. `/candidates` 화면 작성.
7. 관심종목 추가/제외 상태 연결.
8. Telegram digest는 v2로 분리.
