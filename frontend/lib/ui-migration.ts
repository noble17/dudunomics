export type UiMigrationStatus = "absorbed" | "partial" | "todo" | "retire" | "removed";

export type UiMigrationEntry = {
  feature: string;
  legacySurface: string;
  currentCode: string[];
  currentData: string;
  targetSurface: string;
  status: UiMigrationStatus;
  plan: string;
};

export const uiMigrationStatusLabels: Record<UiMigrationStatus, string> = {
  absorbed: "흡수됨",
  partial: "부분 흡수",
  todo: "이동 예정",
  retire: "제거 후보",
  removed: "제거됨",
};

export const uiMigrationEntries: UiMigrationEntry[] = [
  {
    feature: "시장 지표 스트립",
    legacySurface: "이전 통합 화면 상단 시장 지표",
    currentCode: ["frontend/components/market/market-strip.tsx", "frontend/hooks/useQuotes.ts"],
    currentData: "quotesApi.get, /api/quotes",
    targetSurface: "포트폴리오, 종목분석, 전략",
    status: "absorbed",
    plan: "SPY/QQQ/USD/KRW/BTC 등 공통 시장 지표를 주요 화면 상단 MarketStrip으로 흡수했습니다.",
  },
  {
    feature: "관심/보유 종목 quick list",
    legacySurface: "이전 통합 화면의 관심/보유 요약 목록",
    currentCode: ["frontend/components/portfolio/dashboard.tsx", "frontend/app/watchlist/page.tsx"],
    currentData: "holdingsApi.list, /api/holdings",
    targetSurface: "포트폴리오, 관심종목",
    status: "absorbed",
    plan: "보유 기반 quick list는 포트폴리오 보유 테이블로, 관심종목 전용 목록은 /watchlist 흐름으로 흡수했습니다.",
  },
  {
    feature: "단일 종목 차트/뉴스/AI 요약",
    legacySurface: "이전 통합 화면의 종목 차트, 뉴스, AI 요약",
    currentCode: [
      "frontend/components/charts/ticker-candle-chart.tsx",
      "frontend/components/stocks/ticker-insights.tsx",
      "frontend/components/stocks/ticker-detail.tsx",
    ],
    currentData: "candles, newsApi.get, aiApi.summary, aiApi.streamChat",
    targetSurface: "종목분석",
    status: "absorbed",
    plan: "종목 상세 화면에서 차트, 뉴스, 명시 실행형 AI 요약을 한 곳에 제공하도록 흡수했습니다.",
  },
  {
    feature: "보유종목 동기화",
    legacySurface: "이전 통합 화면의 보유종목 동기화",
    currentCode: ["frontend/components/holdings/holdings-editor.tsx", "frontend/app/jobs/page.tsx"],
    currentData: "portfolioApi.current, holdingsApi.syncFromToss, holdingsApi.syncFromKis",
    targetSurface: "포트폴리오 > 보유종목 관리, 관리 > 작업관리",
    status: "absorbed",
    plan: "수동 Toss 가져오기는 보유종목 관리에 유지하고, 예약 동기화/초기 적재는 작업관리로 흡수했습니다. KIS 버튼은 현재 운영 화면에서 제외합니다.",
  },
  {
    feature: "리밸런싱",
    legacySurface: "이전 통합 화면의 리밸런싱 패널",
    currentCode: ["제거됨"],
    currentData: "rebalancingApi.get, rebalancingApi.setTargetWeight",
    targetSurface: "포트폴리오",
    status: "removed",
    plan: "포트폴리오 화면에서 제거했습니다. 목표 비중 기반 리밸런싱은 현재 운영 흐름에서 제외합니다.",
  },
  {
    feature: "성과 분석",
    legacySurface: "이전 통합 화면의 성과 패널",
    currentCode: ["frontend/components/portfolio/performance-summary.tsx"],
    currentData: "performanceApi.get, /api/portfolio/performance",
    targetSurface: "포트폴리오",
    status: "absorbed",
    plan: "자산 추이와 별도로 Sharpe, MDD, 벤치마크 비교를 포트폴리오 성과 분석 섹션으로 통합했습니다.",
  },
  {
    feature: "거래 기록",
    legacySurface: "이전 통합 화면의 거래 기록 패널",
    currentCode: ["frontend/components/portfolio/trade-log-manager.tsx"],
    currentData: "tradesApi.list/create/delete",
    targetSurface: "포트폴리오 > 보유종목 관리",
    status: "absorbed",
    plan: "포트폴리오 보유관리 화면에 거래 추가/삭제 테이블을 옮기고, source별 보유 데이터와 분리해서 보여줍니다.",
  },
  {
    feature: "알림 조건/히스토리",
    legacySurface: "이전 통합 화면의 알림 패널",
    currentCode: ["frontend/components/alerts/alert-manager.tsx", "api/routers/alerts.py", "core/scheduler.py"],
    currentData: "alertsApi, /api/alerts/events, alert_check job",
    targetSurface: "관리 > 작업관리, 관심종목 또는 종목분석",
    status: "absorbed",
    plan: "알림 조건 생성은 종목 상세와 관리 화면에 두고, 최근 발생 이력은 관리 > 알림 관리에서 확인하도록 흡수했습니다.",
  },
  {
    feature: "종목 스크리너",
    legacySurface: "이전 통합 화면의 리서치/스크리너",
    currentCode: ["frontend/app/screener/page.tsx", "frontend/app/growth/page.tsx"],
    currentData: "screenerApi.scores, /api/screener/scores",
    targetSurface: "종목분석",
    status: "absorbed",
    plan: "이미 /screener, /growth가 상단 메뉴의 종목분석 그룹에 묶였으므로 별도 위젯 없이 해당 화면에서 유지합니다.",
  },
  {
    feature: "백테스트",
    legacySurface: "이전 통합 화면의 백테스트 도구",
    currentCode: ["frontend/app/backtest/page.tsx"],
    currentData: "BacktestForm",
    targetSurface: "전략",
    status: "absorbed",
    plan: "/backtest가 이미 독립 화면으로 존재하므로 전략 화면에서 유지합니다.",
  },
  {
    feature: "계산기 도구",
    legacySurface: "이전 통합 화면의 포지션/환율/수익률 계산기",
    currentCode: ["frontend/components/backtest/strategy-tools.tsx"],
    currentData: "fxApi.rate, 로컬 계산",
    targetSurface: "전략 또는 포트폴리오",
    status: "absorbed",
    plan: "포지션 사이징, 환율 변환, 수익률 계산을 전략 화면의 보조 도구로 흡수했습니다.",
  },
  {
    feature: "범용 AI 채팅",
    legacySurface: "이전 통합 화면의 범용 AI 채팅",
    currentCode: ["제거됨"],
    currentData: "aiApi.streamChat",
    targetSurface: "종목분석",
    status: "removed",
    plan: "범용 채팅은 기능 과다라 별도 이식하지 않고 제거했습니다. 종목 상세의 명시 실행형 AI 요약만 유지합니다.",
  },
];
