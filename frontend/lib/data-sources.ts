export type DataSourceStatus = "active" | "fallback" | "planned";

export type DataSourceEntry = {
  area: string;
  surfaces: string[];
  data: string;
  primary: string;
  fallback: string;
  code: string[];
  status: DataSourceStatus;
  tossFit: string;
};

export type ProviderEntry = {
  name: string;
  role: string;
  auth: string;
  code: string[];
  notes: string;
};

export const providerInventory: ProviderEntry[] = [
  {
    name: "KIS Open API",
    role: "국내 목표주가/투자의견 consensus",
    auth: "KIS_APPKEY, KIS_SECRETKEY",
    code: ["core/data/price_target_consensus.py", "core/prices/kis.py"],
    notes: "Toss가 제공하지 않는 국내 증권사 목표주가 영역에만 유지합니다. 시세/환율/OHLCV/잔고의 기본 경로는 Toss입니다.",
  },
  {
    name: "Yahoo Finance",
    role: "뉴스/검색 일부 보조 경로",
    auth: "없음",
    code: ["core/prices/kis.py", "core/data/yf_session.py", "api/routers/news.py"],
    notes: "시세/OHLCV의 조용한 fallback으로 쓰지 않는 방향으로 축소합니다.",
  },
  {
    name: "FMP",
    role: "시장 지표, 미국 목표주가 consensus",
    auth: "FMP_API_KEY",
    code: ["core/data/market_indices.py", "core/data/price_target_consensus.py"],
    notes: "키/요금제 제한이 있어 미국 목표주가는 명시 갱신 경로에서만 호출합니다.",
  },
  {
    name: "Finviz",
    role: "미국 valuation/fundamentals, screener bulk, 목표주가 fallback",
    auth: "없음",
    code: ["core/data/fundamentals_scraper.py", "core/data/finviz_screener.py"],
    notes: "HTML 기반 수집이라 화면 구조 변화에 민감합니다.",
  },
  {
    name: "StockAnalysis",
    role: "미국 연간 재무제표, 현금흐름 보강, 검색 primary, 목표주가 fallback",
    auth: "없음",
    code: ["core/data/stockanalysis_financials.py", "core/data/search_provider.py"],
    notes: "SvelteKit embedded data를 파싱합니다.",
  },
  {
    name: "Naver Finance",
    role: "국내 PER/PBR/EPS/시총/업종, 국내 분기 재무",
    auth: "없음",
    code: ["core/data/naver_fundamentals.py", "core/data/naver_quarterly.py"],
    notes: "국내 종목 기본/분기 데이터 보강에 사용합니다.",
  },
  {
    name: "OpenDART",
    role: "국내 성장주 필수 재무 지표",
    auth: "DART_API_KEY",
    code: ["core/data/dart_fundamentals.py", "core/batch_refresh.py"],
    notes: "국내 성장주 batch에는 키가 필요합니다.",
  },
  {
    name: "Upbit",
    role: "BTC/KRW 현재가",
    auth: "없음",
    code: ["core/prices/upbit.py", "api/routers/quotes.py"],
    notes: "상단 quote strip의 BTC 가격에 사용합니다.",
  },
  {
    name: "Toss OpenAPI",
    role: "현재가, 캔들, 환율, 계좌/보유종목, 매수 가능 현금, 주문, 호가, 체결, 장운영 정보",
    auth: "TOSS_CLIENT_ID, TOSS_CLIENT_SECRET, TOSS_ACCOUNT_SEQ",
    code: ["core/prices/toss.py", "api/routers/holdings.py", "core/scheduler.py"],
    notes: "Toss 키가 있으면 시세/환율/OHLCV provider 기본값으로 사용하고, 보유종목/현금은 수동 또는 예약 동기화로 가져옵니다.",
  },
];

export const dataSourceEntries: DataSourceEntry[] = [
  {
    area: "상단 지표/Quotes",
    surfaces: ["/portfolio", "/stocks", "/backtest", "MarketStrip"],
    data: "SPY, QQQ, USD/KRW, BTC, DJI, VIX, US10Y, WTI, GOLD",
    primary: "Toss OpenAPI, Upbit, FMP",
    fallback: "없음 또는 명시 오류 표시",
    code: ["api/routers/quotes.py", "core/fx.py", "core/data/market_indices.py"],
    status: "active",
    tossFit: "Toss 키가 있으면 현재가와 USD/KRW 환율은 Toss OpenAPI를 기본 사용합니다. BTC와 원자재/금리 지표는 별도 유지가 필요합니다.",
  },
  {
    area: "캔들/차트",
    surfaces: ["/watchlist", "/stocks", "/screener/[ticker]"],
    data: "일봉 OHLCV, 이동평균, 거래량",
    primary: "DuckDB prices_cache, Toss OpenAPI",
    fallback: "MARKET_DATA_PROVIDER=kis 명시 설정 시에만 KIS/FDR 보조",
    code: ["api/routers/candles.py", "core/data/ohlcv_cache.py", "api/routers/stock_detail.py"],
    status: "active",
    tossFit: "Toss 키가 있으면 Toss candles를 OHLCV provider 기본값으로 사용합니다. MARKET_DATA_PROVIDER=kis를 명시하면 기존 KIS 경로를 사용할 수 있습니다.",
  },
  {
    area: "보유종목/포트폴리오",
    surfaces: ["/portfolio", "/portfolio/holdings"],
    data: "보유 수량, 평균단가, 현금, 평가금액, 수익률",
    primary: "DuckDB holdings/holding_sources/trades/meta, Toss 동기화",
    fallback: "수동 입력",
    code: ["api/routers/holdings.py", "api/routers/portfolio.py", "core/repository.py"],
    status: "active",
    tossFit: "보유종목 편집 화면은 source별 행을 분리하고, 포트폴리오 계산에서만 합산합니다. 동기화 종목은 포트폴리오 숨김 플래그로 계산에서 제외할 수 있습니다. 현금도 manual/toss를 분리 저장한 뒤 계산 시 합산합니다.",
  },
  {
    area: "거래 기록",
    surfaces: ["/portfolio/holdings"],
    data: "매수/매도 로그, 거래 기반 holdings 재계산",
    primary: "DuckDB trades, Toss 주문 목록",
    fallback: "수동 입력",
    code: ["api/routers/trades.py", "core/repository.py", "core/prices/toss.py"],
    status: "active",
    tossFit: "Toss 주문 목록에서 조회 가능한 체결분을 source=toss 거래로 저장합니다. 현재 OpenAPI 문서상 CLOSED 주문 목록은 미지원이라 OPEN/부분체결 중심으로 동기화합니다.",
  },
  {
    area: "종목 검색/기본 정보",
    surfaces: ["/holdings", "/stocks", "/watchlist"],
    data: "symbol, 종목명, 거래소, 통화, market",
    primary: "StockAnalysis search, Toss stocks lookup",
    fallback: "Yahoo Finance autocomplete",
    code: ["core/data/search_provider.py", "core/prices/toss.py", "api/routers/holdings.py"],
    status: "active",
    tossFit: "보유종목 lookup은 Toss stocks로 대체했습니다. 종목명 검색은 Toss 검색 API가 없어 StockAnalysis/Yahoo 검색 provider를 유지합니다.",
  },
  {
    area: "뉴스",
    surfaces: ["/stocks"],
    data: "종목 뉴스 제목, 발행시각, 링크, 이미지",
    primary: "Google News RSS, Yahoo RSS",
    fallback: "yfinance Ticker.news",
    code: ["api/routers/news.py", "core/data/news_provider.py"],
    status: "active",
    tossFit: "Toss 문서에는 뉴스 API가 없어 유지 대상입니다.",
  },
  {
    area: "미국 재무/Valuation",
    surfaces: ["/screener", "/growth", "/stocks"],
    data: "PER, PBR, PEG, margins, cash flow, annual financials",
    primary: "DuckDB fundamental_snapshots, Finviz/StockAnalysis 수집 작업",
    fallback: "화면 조회 중 자동 fallback 없음",
    code: ["core/data/fundamental_backfill.py", "core/data/fundamentals_scraper.py", "core/data/stockanalysis_financials.py"],
    status: "active",
    tossFit: "Toss는 재무제표를 제공하지 않으므로 유지 대상입니다.",
  },
  {
    area: "국내 재무/성장주",
    surfaces: ["/growth", "/screener"],
    data: "PER/PBR/EPS/시총/업종, 분기 재무, DART 기반 품질 지표",
    primary: "DuckDB fundamental_snapshots/quant_scores, Naver Finance, OpenDART 수집 작업",
    fallback: "DART 키 없으면 coverage 경고",
    code: ["core/data/naver_fundamentals.py", "core/data/naver_quarterly.py", "core/data/dart_fundamentals.py"],
    status: "active",
    tossFit: "Toss stocks는 기본 정보 보강에는 유용하지만 재무 지표 대체는 어렵습니다.",
  },
  {
    area: "목표주가 Consensus",
    surfaces: ["/growth", "/screener/[ticker]"],
    data: "미국/국내 목표주가, analyst consensus",
    primary: "미국 FMP 명시 갱신, 국내 KIS Open API 명시 갱신",
    fallback: "Finviz, StockAnalysis는 fallback_used 표시가 가능한 경우에만",
    code: ["core/data/price_target_consensus.py"],
    status: "active",
    tossFit: "Toss 문서에는 목표주가 API가 없어 유지 대상입니다.",
  },
  {
    area: "Toss 적용 범위",
    surfaces: ["provider layer"],
    data: "prices, candles, exchange-rate, holdings, buying-power, stocks, orders, orderbook, trades, market-calendar",
    primary: "Toss OpenAPI",
    fallback: "KIS는 국내 목표주가에만 유지, 나머지는 명시 설정/명시 갱신",
    code: ["core/prices/toss.py", "api/routers/holdings.py", "core/scheduler.py"],
    status: "active",
    tossFit: "시세/환율/캔들/보유종목/현금/보유종목 lookup과 조회 가능한 주문 체결분까지 Toss로 적용했습니다. KIS 동기화 API는 Toss 대체 안내만 반환합니다.",
  },
];

export const sourceStatusLabels: Record<DataSourceStatus, string> = {
  active: "사용 중",
  fallback: "보조",
  planned: "예정",
};
