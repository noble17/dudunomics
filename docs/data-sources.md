# Dudunomics 데이터 출처 인벤토리

작성일: 2026-06-06

이 문서는 Dudunomics가 어떤 데이터를 어디서 가져오는지 정리한 기준 문서입니다. 앱 내부 요약 화면은 `/data-sources`에 있습니다.

## 요약

| Provider | 역할 | 인증 | 주요 코드 |
| --- | --- | --- | --- |
| KIS Open API | 국내 목표주가/투자의견 consensus | `KIS_APPKEY`, `KIS_SECRETKEY` | `core/data/price_target_consensus.py`, `core/prices/kis.py` |
| Yahoo Finance | 뉴스/검색 일부 보조 경로 | 없음 | `core/data/yf_session.py`, `api/routers/news.py` |
| FMP | 시장 지표, 미국 목표주가 consensus | `FMP_API_KEY` | `core/data/market_indices.py`, `core/data/price_target_consensus.py` |
| Finviz | 미국 valuation/fundamentals, screener bulk, 목표주가 fallback | 없음 | `core/data/fundamentals_scraper.py`, `core/data/finviz_screener.py` |
| StockAnalysis | 미국 연간 재무제표, 현금흐름 보강, 검색 primary, 목표주가 fallback | 없음 | `core/data/stockanalysis_financials.py`, `core/data/search_provider.py` |
| Naver Finance | 국내 PER/PBR/EPS/시총/업종, 국내 분기 재무 | 없음 | `core/data/naver_fundamentals.py`, `core/data/naver_quarterly.py` |
| OpenDART | 국내 성장주 필수 재무 지표 | `DART_API_KEY` | `core/data/dart_fundamentals.py`, `core/batch_refresh.py` |
| Upbit | BTC/KRW 현재가 | 없음 | `core/prices/upbit.py`, `api/routers/quotes.py` |
| Toss OpenAPI | 현재가, 캔들, 환율, 계좌/보유종목, 매수 가능 현금, 주문, 호가, 체결, 장운영 정보 | `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, `TOSS_ACCOUNT_SEQ` | `core/prices/toss.py`, `api/routers/holdings.py`, `core/scheduler.py` |

## 기능별 데이터 흐름

| 영역 | 화면/API | 데이터 | 현재 출처 | Fallback | Toss 적용성 |
| --- | --- | --- | --- | --- | --- |
| 상단 지표/Quotes | `/portfolio`, `/stocks`, `/backtest`, `MarketStrip` | SPY, QQQ, USD/KRW, BTC, DJI, VIX, US10Y, WTI, GOLD | Toss OpenAPI, Upbit, FMP | 없음 또는 명시 오류 표시 | Toss 키가 있으면 현재가와 USD/KRW 환율은 Toss OpenAPI를 기본 사용합니다. BTC와 원자재/금리 지표는 별도 유지가 필요합니다. |
| 캔들/차트 | `/watchlist`, `/stocks`, `/screener/[ticker]` | 일봉 OHLCV, 이동평균, 거래량 | DuckDB `prices_cache`, Toss OpenAPI | `MARKET_DATA_PROVIDER=kis` 명시 설정 시에만 KIS/FDR 보조 | Toss 키가 있으면 Toss candles를 OHLCV provider 기본값으로 사용합니다. 화면 조회는 `cache_only`를 원칙으로 합니다. |
| 보유종목/포트폴리오 | `/portfolio`, `/portfolio/holdings` | 보유 수량, 평균단가, 현금, 평가금액, 수익률 | DuckDB `holdings`/`holding_sources`/`trades`/`meta`, Toss 동기화 | 수동 입력 | 보유종목 편집 화면은 source별 행을 분리하고, 포트폴리오 계산에서만 합산합니다. 동기화 종목은 포트폴리오 숨김 플래그로 계산에서 제외할 수 있습니다. 현금도 `manual`/`toss`를 분리 저장한 뒤 계산 시 합산합니다. |
| 거래 기록 | `/portfolio/holdings` | 매수/매도 로그, 거래 기반 holdings 재계산 | DuckDB `trades` | 수동 입력 | Toss 주문 목록/상세 API를 붙이면 실제 주문과 체결 조회로 확장할 수 있습니다. |
| 종목 검색/기본 정보 | `/holdings`, `/stocks`, `/watchlist` | symbol, 종목명, 거래소, 통화, market | StockAnalysis search, Toss stocks lookup | Yahoo Finance autocomplete | 보유종목 lookup은 Toss stocks로 대체했습니다. 종목명 검색은 Toss 검색 API가 없어 StockAnalysis/Yahoo 검색 provider를 유지합니다. |
| 뉴스 | `/stocks` | 종목 뉴스 제목, 발행시각, 링크, 이미지 | Google News RSS, Yahoo RSS | yfinance `Ticker.news` | Toss 문서에는 뉴스 API가 없어 유지 대상입니다. |
| 미국 재무/Valuation | `/screener`, `/growth`, `/stocks` | PER, PBR, PEG, margins, cash flow, annual financials | DuckDB `fundamental_snapshots`, Finviz/StockAnalysis 수집 작업 | 화면 조회 중 자동 fallback 없음 | Toss는 재무제표를 제공하지 않으므로 유지 대상입니다. |
| 국내 재무/성장주 | `/growth`, `/screener` | PER/PBR/EPS/시총/업종, 분기 재무, DART 기반 품질 지표 | DuckDB `fundamental_snapshots`/`quant_scores`, Naver Finance, OpenDART 수집 작업 | DART 키 없으면 coverage 경고 | Toss stocks는 기본 정보 보강에는 유용하지만 재무 지표 대체는 어렵습니다. |
| 목표주가 Consensus | `/growth`, `/screener/[ticker]` | 미국/국내 목표주가, analyst consensus | 미국 FMP 명시 갱신, 국내 KIS Open API 명시 갱신 | Finviz, StockAnalysis는 `fallback_used` 표시가 가능한 경우에만 | Toss 문서에는 목표주가 API가 없어 유지 대상입니다. |
| Toss 적용 범위 | provider layer | prices, candles, exchange-rate, holdings, buying-power, stocks, orders, orderbook, trades, market-calendar | Toss OpenAPI | KIS는 국내 목표주가에만 유지, 나머지는 명시 설정/명시 갱신 | 시세/환율/캔들/보유종목/현금/보유종목 lookup까지 Toss로 적용했습니다. KIS 동기화 API는 Toss 대체 안내만 반환합니다. |

## Toss OpenAPI 적용 우선순위

1. `core/prices/toss.py` 추가
   - OAuth2 Client Credentials 토큰 발급과 파일/메모리 캐시를 구현합니다.
   - `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET` 환경변수를 사용합니다.
   - 계좌 API는 `TOSS_ACCOUNT_SEQ`를 `X-Tossinvest-Account` 헤더로 전달합니다.

2. 시세/환율/캔들 병렬 provider
   - `GET /api/v1/prices`: 현재가 다건 조회
   - `GET /api/v1/exchange-rate`: KRW/USD 환율
   - `GET /api/v1/candles`: 1분봉/일봉 OHLCV
   - Toss 키가 있으면 Toss provider를 기본으로 사용합니다.
   - `MARKET_DATA_PROVIDER=kis`를 명시한 운영자 설정에서만 기존 KIS provider를 보조 경로로 사용할 수 있습니다.

3. 보유종목/현금 동기화
   - `GET /api/v1/accounts`: 사용 가능한 계좌 확인
   - `GET /api/v1/holdings`: 보유 종목과 평가 정보 조회
   - `GET /api/v1/buying-power`: KRW/USD 매수 가능 현금 조회
   - `/api/holdings/sync-from-toss`를 제공합니다.
   - 기존 `/api/holdings/sync-from-kis`는 Toss 대체 안내만 반환합니다.
   - `TOSS_HOLDINGS_SYNC_ENABLED=true`이면 APScheduler가 `TOSS_HOLDINGS_SYNC_INTERVAL_MINUTES` 주기로 자동 동기화합니다.
   - `source=toss` 보유분은 화면에서 직접 수정하지 않고, 수동 보유분은 `source=manual`로 별도 저장합니다.
   - 같은 티커가 수동/Toss에 모두 있어도 `/holdings`에서는 두 행으로 보여주고, `/portfolio` 계산에서만 수량과 평균단가를 합산합니다.
   - `excluded_from_portfolio=true`인 동기화 보유분은 `/holdings`에는 남기고 `/portfolio` 집계에서는 제외합니다.
   - 현금은 `cash_krw_manual`/`cash_usd_manual`, `cash_krw_toss`/`cash_usd_toss`처럼 출처별로 저장하고 합산값만 포트폴리오 계산에 사용합니다.

5. 펀더멘털 snapshot 적재
   - `fundamental_snapshots_hydrate` 작업이 관심종목과 보유종목의 미국/해외 티커를 모아 Finviz/StockAnalysis 데이터를 `fundamental_snapshots`에 저장합니다.
   - 화면 조회는 이 snapshot을 읽고, 데이터가 없으면 외부 호출 대신 `데이터 보강 필요` 상태를 표시합니다.
   - 국내 티커는 이 작업에서 제외하고 Naver/OpenDART 배치로 처리합니다.

4. 주문 기능은 별도 단계
   - `POST /api/v1/orders`, modify, cancel, order history, buying power, sellable quantity, commissions를 사용합니다.
   - 실제 주문은 별도 확인 UI, 주문 금액/수량 검증, 장 운영 시간 안내가 필요합니다.

## 유지 대상

- 뉴스: Toss OpenAPI 문서에 뉴스 API가 없습니다.
- 미국/국내 재무제표: Toss OpenAPI 문서에 재무제표 API가 없습니다.
- 목표주가 consensus: Toss OpenAPI 문서에 목표주가 API가 없습니다.
- BTC/KRW, 원자재, 금리 지표: Toss 주식 API 범위 밖입니다.

## 관련 문서

- Toss OpenAPI 개요: `https://openapi.tossinvest.com/openapi-docs/overview.md`
- Toss OpenAPI reference: `https://openapi.tossinvest.com/openapi-docs/latest/api-reference/README.md`
- Toss OpenAPI JSON: `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`
