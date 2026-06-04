# 공통 종목 데이터 레이어 v1 설계

## 배경

현재 Dudunomics는 `/portfolio`, `/watchlist`, `/growth`, `/screener`, `/terminal`이 각각 유용한 기능을 갖고 있지만, 데이터 조회 경로가 점점 페이지별로 퍼질 위험이 있다. 특히 가격/OHLCV, 펀더멘털/밸류에이션, 기술지표, 성장주 점수, Watchlist 상세가 서로 같은 종목 정보를 사용하면서도 일부는 배치 데이터, 일부는 즉석 조회, 일부는 캐시를 읽는다.

이번 리팩토링의 목표는 페이지가 데이터를 직접 수집하지 않게 하고, 공통 종목 데이터 레이어를 중심으로 모든 화면이 같은 데이터를 읽도록 정리하는 것이다.

## 확정 범위

사용자와 합의한 v1 범위는 B안이다.

- 포함: 가격/OHLCV + 기술지표 + 펀더멘털/밸류에이션 공통화
- 제외: 목표주가/애널리스트 컨센서스 공통 캐시 완성
- 유지: Watchlist 상세 UX는 유지하되 데이터 출처를 공통화
- 활용: Terminal의 `lightweight-charts` 차트를 공통 차트 컴포넌트로 승격

목표주가/FMP/Finviz price target은 API 제한과 출처 안정성 이슈가 크므로 v2에서 별도 `price_target_consensus_cache`로 다룬다.

## 완료 정의

v1 완료는 다음 조건으로 판단한다.

- `/api/candles` 같은 일반 조회 API는 외부 API를 호출하지 않고 DB 캐시만 읽는다.
- 명시적 `데이터 보강` 또는 배치만 외부 수집을 실행한다.
- 가격/OHLCV는 KIS 우선 경로로 `prices_cache`에 저장된다.
- 펀더멘털/밸류에이션은 공통 snapshot/cache에 저장되고 `/growth`, `/watchlist`, `/screener`, 신규 종목검색 화면이 같은 값을 읽는다.
- Watchlist와 Portfolio는 종목 목록/보유 정보만 관리하고, 종목 상세 데이터는 공통 레이어에서 읽는다.
- Terminal의 캔들 차트는 공통 컴포넌트가 되어 종목검색 및 Watchlist 상세에서 재사용된다.
- 데이터가 없거나 부족하면 UI에 `마지막 갱신`, `보유 구간`, `부족한 항목`, `마지막 오류`가 표시된다.

## 데이터 분리 원칙

공통 데이터라는 개념은 하나지만, DB 테이블은 데이터 성격별로 나눈다.

가격/OHLCV는 매일 또는 장중 갱신된다. `prices_cache`를 유지하고, ticker/date 기준으로 누적한다.

펀더멘털/밸류에이션은 가격보다 갱신 주기가 느리다. PER, PBR, PSR, PEG, Forward PER, Forward EPS, ROE, ROIC, margin, debt ratio, current ratio, revenue growth, EPS growth 같은 값은 별도 snapshot에 저장한다.

Quant/Growth score는 원천 데이터가 아니라 계산 결과다. `quant_scores`에는 공식 배치 결과만 저장한다. 즉석 조회값이나 임시 fallback 값을 `quant_scores`에 섞지 않는다.

Watchlist와 Portfolio는 사용자 의사결정/보유 상태다. 종목 데이터 자체를 저장하지 않고, ticker/universe/name/memo/holding/trade 같은 사용자 상태만 저장한다.

## 제안 DB 구조

기존 테이블은 유지한다.

- `prices_cache`: OHLCV 일봉 저장
- `quant_scores`: 공식 screener/growth 배치 점수
- `quarterly_financials`: 분기 재무 저장
- `watchlists`, `watchlist_items`: 관심종목 그룹과 항목
- `holdings`, `trades`, `portfolio_snapshots`: 실제 보유/거래/포트폴리오 기록

v1에서 추가 또는 정리할 공통 테이블은 다음이다.

### `ticker_profiles`

종목의 안정적인 메타 정보를 저장한다.

- `ticker`
- `name`
- `market`
- `country`
- `currency`
- `sector`
- `industry`
- `exchange`
- `source`
- `updated_at`

### `fundamental_snapshots`

펀더멘털/밸류에이션 원천값을 날짜 기준으로 저장한다.

- `ticker`
- `as_of`
- `source`
- `per`
- `pbr`
- `psr`
- `peg`
- `forward_pe`
- `trailing_pe`
- `forward_eps`
- `eps_ttm`
- `roe`
- `roic`
- `debt_ratio`
- `current_ratio`
- `gross_margin`
- `operating_margin`
- `revenue_growth`
- `eps_growth`
- `market_cap`
- `raw_json`
- `fetched_at`
- primary key: `(ticker, as_of, source)`

### `ticker_data_status`

각 데이터 종류의 커버리지와 오류 상태를 저장한다.

- `ticker`
- `data_type`: `ohlcv`, `fundamental`, `quarterly`, `quant`
- `source`
- `min_date`
- `max_date`
- `last_fetched_at`
- `last_success_at`
- `last_error`
- `coverage_json`
- primary key: `(ticker, data_type, source)`

이 테이블은 UI가 “왜 데이터가 안 보이는지” 설명하는 기준이 된다.

## 데이터 소스 정책

v1 기본 정책은 다음과 같다.

- UI 일반 조회는 외부 API를 호출하지 않는다.
- 외부 수집은 명시적 `데이터 보강` 버튼 또는 배치에서만 실행한다.
- OHLCV는 KIS 우선으로 수집한다.
- KIS에서 수집 가능한 가격 데이터는 yfinance를 쓰지 않는다.
- yfinance는 v1 OHLCV 기본 경로에서 제외한다.
- Finviz/StockAnalysis는 펀더멘털 보강에 사용할 수 있지만, 조회 결과는 공통 cache/snapshot에 저장한다.
- FMP처럼 사용량 제한이 큰 API는 v1 공통 레이어의 기본 경로에서 제외하고 v2 목표주가 캐시에 한정한다.
- 데이터 소스 실패는 조용히 `-`로 숨기지 않고 `ticker_data_status.last_error`에 남긴다.

## 공통 서비스 구조

신규 서비스 계층을 만든다.

### `core/data/ticker_data_service.py`

종목 데이터 조회의 단일 진입점이다.

주요 함수:

- `get_ticker_overview(ticker, *, cache_only=True)`
- `get_price_history(ticker, start, end, *, cache_only=True)`
- `get_fundamentals(ticker, *, cache_only=True)`
- `hydrate_ticker_data(ticker, scopes)`
- `get_data_status(ticker)`

`hydrate_ticker_data`의 `scopes`는 `ohlcv`, `fundamental`, `quarterly`처럼 명시한다. 이렇게 해야 “차트만 보고 싶은데 펀더멘털까지 긁는” 문제가 생기지 않는다.

### 읽기/쓰기 분리

조회 API는 cache-only이다.

- `/api/candles`
- `/api/watchlists/{id}/items`
- `/api/growth/ticker/{ticker}/valuation`
- `/api/growth/ticker/{ticker}/timing`
- 신규 `/api/tickers/{ticker}/overview`

수집 API만 외부 호출을 허용한다.

- `/api/tickers/{ticker}/hydrate`
- `/api/growth/ticker/{ticker}/hydrate`
- 배치 job

## 종목검색 화면

신규 화면을 만든다.

경로 후보는 `/stocks`이다. 이 화면은 특정 탭의 부속 기능이 아니라 종목 중심 허브다.

구성:

- 검색창: 티커/종목명 검색
- 상단 요약: 회사명, 티커, 가격, 등락률, 시장, 섹터, 시총
- 메인 차트: Terminal의 `lightweight-charts` 기반 차트
- 주요 카드: Valuation Check, Timing Check, 펀더멘털 요약, 데이터 상태
- 행동 버튼: Watchlist 추가, Portfolio 편입/매수 기록, 좋은종목찾기 분석 보기, 백테스트 실행

이 화면은 Watchlist와 Portfolio의 상세 패널과 같은 공통 상세 컴포넌트를 사용한다.

## Terminal 차트 재사용

현재 Terminal의 `frontend/components/terminal/widgets/CandleChart.tsx`는 자산 가치가 높다. v1에서는 이 컴포넌트를 직접 복사하지 않고 공통 차트 컴포넌트로 승격한다.

제안 위치:

- `frontend/components/charts/ticker-candle-chart.tsx`

이 컴포넌트는 다음 입력을 받는다.

- `ticker`
- `defaultPeriod`
- `showIndicators`
- `refreshKey`

Terminal은 이 공통 차트를 사용하도록 바꾸고, Watchlist와 신규 `/stocks`도 같은 컴포넌트를 사용한다.

## Watchlist 적용

Watchlist는 현재 방향을 유지한다.

- 여러 Watchlist 관리
- 하나의 종목이 여러 Watchlist에 포함 가능
- Performance View로 종목 비교
- 종목 클릭 시 상세정보 표시

변경되는 점:

- Watchlist 상세의 차트/valuation/timing은 공통 종목 상세 컴포넌트를 사용한다.
- Watchlist 항목 API는 종목 목록과 비교 지표만 반환한다.
- 상세 데이터는 공통 ticker API에서 읽는다.
- `데이터 보강`은 현재 선택 종목의 필요한 scope만 수집한다.

## Portfolio 적용

Portfolio는 실제 보유/거래 중심으로 남긴다.

- holdings/trades/portfolio snapshots는 그대로 유지
- Performance View는 공통 가격 데이터에서 계산
- 보유 종목 클릭 시 Watchlist와 같은 공통 상세 컴포넌트 표시 가능
- Portfolio가 펀더멘털을 별도로 수집하지 않는다.

## Growth/Screener 적용

`/growth`와 `/screener`는 공식 점수 화면이다.

- 원천 데이터는 공통 cache에서 읽는다.
- 배치는 공통 cache를 보강한 뒤 `quant_scores`를 계산한다.
- 화면 조회는 `quant_scores`와 공통 상세 데이터를 조합한다.
- 즉석 fallback 값을 `quant_scores`에 저장하지 않는다.

## 배치 전략

v1 배치는 다음 순서로 간다.

1. universe ticker 목록 확정
2. 가격/OHLCV 보강
3. 펀더멘털/밸류에이션 보강
4. 분기 재무 보강
5. quant/growth score 계산
6. `ticker_data_status` 갱신

사용자가 명시적으로 보강 버튼을 누른 경우는 해당 종목만 scope 단위로 보강한다.

## 에러와 UI 표시

데이터가 없을 때는 다음처럼 구분한다.

- 캐시 없음: 아직 수집한 적 없음
- 데이터 부족: 수집했지만 요청 구간이 부족함
- API 실패: 마지막 수집 시 외부 API 오류
- 제한/미지원: API 제한 또는 해당 종목/시장 미지원

UI에는 다음 항목을 보여준다.

- 마지막 성공 시각
- 가격 데이터 보유 구간
- 펀더멘털 마지막 기준일
- 부족한 항목
- 마지막 오류 메시지

## 구현 단계

### Phase 1: 현재 데이터 경로 감사

- 가격/OHLCV 호출 경로 목록화
- 펀더멘털/밸류에이션 호출 경로 목록화
- 즉석 외부 호출 위치 목록화
- yfinance/FMP 등 제한 소스 사용 위치 표시

### Phase 2: 공통 스키마 추가

- `ticker_profiles`
- `fundamental_snapshots`
- `ticker_data_status`
- repository 함수 추가

### Phase 3: TickerDataService 추가

- cache-only 조회 함수
- scope 기반 hydrate 함수
- status 갱신 함수

### Phase 4: API 읽기/쓰기 분리

- `/api/candles` cache-only 유지
- 신규 `/api/tickers/{ticker}/overview`
- 신규 `/api/tickers/{ticker}/hydrate`
- growth/watchlist hydrate는 공통 hydrate로 위임

### Phase 5: Terminal 차트 공통화

- Terminal CandleChart를 공통 차트로 이동
- Terminal 기존 화면은 공통 차트를 재사용
- Watchlist 상세와 신규 종목검색 화면에 적용

### Phase 6: 신규 종목검색 화면

- `/stocks` 신설
- 검색, 개요, 차트, Valuation Check, Timing Check, 행동 버튼 구성

### Phase 7: Watchlist/Portfolio/Growth/Screener 연결

- Watchlist 상세를 공통 종목 상세로 교체
- Portfolio 보유 종목 상세에 공통 종목 상세 적용
- Growth/Screener 상세 조회는 공통 데이터 레이어를 사용

### Phase 8: 검증

- unit: repository, TickerDataService, cache-only 정책
- API: candles, tickers overview/hydrate, watchlist items
- UI: `/stocks`, `/watchlist`, `/portfolio`, `/growth`
- 브라우저 검증: 데이터 없음/부족/보강 성공/보강 실패 상태 확인

## 리스크와 대응

작업 범위가 넓다. 그래서 한 번에 모든 페이지를 바꾸지 않고, 공통 레이어를 먼저 만든 뒤 화면을 하나씩 연결한다.

DuckDB 파일 락 문제가 있다. 앱 프로세스 실행 중 직접 DB 검사에 제한이 있으므로 API 기반 검증과 테스트 DB 검증을 병행한다.

KIS 해외 OHLCV의 시장/거래소 매핑이 종목마다 다를 수 있다. `ticker_profiles`에 exchange/source를 저장해 재조회 시 추정 비용을 줄인다.

펀더멘털 출처가 시장별로 다르다. 국내는 DART/Naver, 해외는 Finviz/StockAnalysis를 우선 사용하되 source와 fetched_at을 반드시 저장한다.

## 제외 범위

v1에서는 다음을 하지 않는다.

- 목표주가 컨센서스 캐시 완성
- FMP 중심 데이터 수집
- yfinance OHLCV 기본 경로 복구
- 전체 DB 재생성
- 기존 Terminal 제거
- Portfolio 거래/손익 구조 대개편

## 권장 결정

이 설계의 핵심 결정은 “UI 조회는 캐시만 읽고, 수집은 버튼/배치만 한다”이다. 이 원칙을 지키면 페이지가 늘어나도 데이터 경로가 복잡해지지 않는다.

v1 구현은 공통 데이터 레이어와 `/stocks` 종목검색 허브를 먼저 만들고, 이후 Watchlist 상세를 공통 상세 컴포넌트로 교체하는 순서가 가장 안전하다.
