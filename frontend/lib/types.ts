export interface HoldingIn {
  name: string;
  currency: "KRW" | "USD";
  quantity: number;
  avg_price: number;
  sector?: string;
  market?: string;
}

export interface TickerLookupOut {
  ticker: string;
  name: string;
  market: string;
  currency: string;
}

export interface TickerSearchHit {
  ticker: string;
  name: string;
  exchange: string;
  market: string;
  type: string;
}

export interface HoldingOut extends HoldingIn {
  ticker: string;
  updated_at: string;
}

export interface EventOut {
  id: number;
  ts: string;
  label: string;
  amount: number;
  type: string;
}

export interface CashUpdate {
  cash_krw: number;
  cash_usd: number;
}

export interface PortfolioRow {
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  currency: string;
  market_value_krw: number;
  return_pct: number;
  weight_pct: number;
  sector?: string;
}

export interface PortfolioSnapshot {
  rows: PortfolioRow[];
  total_equity_krw: number;
  total_with_cash_krw: number;
  total_equity_usd: number;
  total_with_cash_usd: number;
  cash_krw: number;
  cash_usd: number;
  usdkrw: number;
  updated_at: string;
}

export interface SnapshotHistory {
  ts: string;
  total_equity_krw: number;
  total_with_cash_krw: number;
  total_equity_usd: number;
  total_with_cash_usd: number;
}

export interface StrategyDef {
  name: string;
  params_schema: Record<string, {
    type: string;
    default: number;
    label: string;
    min?: number;
    max?: number;
    options?: string[];
  }>;
  engine: string;
  supports_risk_options: boolean;
  description?: string;
  icon?: string;
  tags?: string[];
}

export interface RiskOptions {
  market_filter?: boolean;
  market_filter_index?: "auto" | "spy" | "kospi";
  market_filter_ma_days?: number;
  market_filter_reduction?: number;
  weighting?: "equal" | "inverse_vol";
  vol_lookback_days?: number;
}

export interface BacktestRunIn {
  ticker?: string;
  tickers?: string[];
  strategy: string;
  params: Record<string, number | string>;
  period_start: string;
  period_end: string;
  risk_options?: RiskOptions;
}

export interface BacktestRunOut {
  id: number;
  ticker: string;
  strategy: string;
  params: Record<string, number | string>;
  period_start: string;
  period_end: string;
  total_return: number;
  mdd: number;
  sharpe: number;
  equity_curve: Array<{ ts: string; equity: number }>;
  created_at: string;
  // 1단계 이후 Optional
  tickers?: string[];
  cagr?: number;
  per_ticker_contribution?: Record<string, number>;
  weights_history?: Array<Record<string, number | string>>;
  rebalance_log?: Array<Record<string, unknown>>;
  warnings?: string[];
}

export interface QuantScore {
  ticker: string;
  universe: string;
  as_of: string;
  company_name: string | null;
  pct_momentum: number | null;
  pct_valuation: number | null;
  pct_eps_momentum: number | null;
  pct_quality: number | null;
  pct_technical: number | null;
  raw_momentum: number | null;
  raw_fwd_pe: number | null;
  raw_pbr: number | null;
  raw_psr: number | null;
  raw_trailing_pe: number | null;
  raw_eps_ttm: number | null;
  raw_fwd_eps: number | null;
  raw_roe: number | null;
  raw_debt_ratio: number | null;
  raw_rsi: number | null;
  above_ma200: boolean | null;
  cfo_positive: boolean | null;
  sector: string | null;
  industry: string | null;
}

export interface FactorWeights {
  momentum: number;
  valuation: number;
  eps_momentum: number;
  quality: number;
  technical: number;
}

export interface TickerNote {
  ticker: string;
  opinion: string | null;
  target_price: number | null;
  memo: string | null;
  tags: string | null;
  updated_at: string | null;
}

export interface WidgetItem {
  i: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WorkspaceLayout {
  panels?: [number, number, number];
  center_widgets?: WidgetItem[];
  left_widget?: string | null;
  right_widget?: string | null;
}

export interface QuoteItem {
  price: number
  change_abs: number
  change_pct: number
}

export interface QuotesOut {
  SPY: QuoteItem | null
  QQQ: QuoteItem | null
  USDKRW: QuoteItem | null
  BTC: QuoteItem | null
  DJI: QuoteItem | null
  VIX: QuoteItem | null
  US10Y: QuoteItem | null
  WTI: QuoteItem | null
  GOLD: QuoteItem | null
}

// ── 지표 ──────────────────────────────────────────────────
export interface IndicatorPoint {
  time: string
  value: number
}

export interface IndicatorsData {
  ma: Record<string, IndicatorPoint[]>        // "5" | "20" | "60" | "120"
  bollinger: Record<string, IndicatorPoint[]> // "upper" | "middle" | "lower"
  rsi: IndicatorPoint[]
  macd: Record<string, IndicatorPoint[]>      // "macd" | "signal" | "histogram"
  volume_ma: IndicatorPoint[]
}

export interface CandleItem {
  time: string;   // "YYYY-MM-DD"
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandlesOut {
  ticker: string;
  period: string;
  candles: CandleItem[];
  indicators?: IndicatorsData | null;
}

export interface NewsItem {
  title: string;
  published_date: string;
  url: string;
  site: string;
  image: string | null;
}

export interface NewsOut {
  ticker: string;
  items: NewsItem[];
}

export interface AISummaryOut {
  ticker: string;
  summary: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── 알림 ──────────────────────────────────────────────────
export type AlertConditionType =
  | "price_above"
  | "price_below"
  | "rsi_above"
  | "rsi_below"
  | "ma_golden_cross"
  | "ma_dead_cross"

export interface AlertCondition {
  id: number
  ticker: string
  condition_type: AlertConditionType
  condition_value: number | null
  enabled: boolean
  created_at: string
}

export interface AlertEvent {
  id: number
  ticker: string
  condition_type: string
  condition_value: number | null
  triggered_price: number
  triggered_at: string
  read: boolean
}

export interface AlertIn {
  ticker: string
  condition_type: AlertConditionType
  condition_value?: number | null
}

// ── M8 Trades ──────────────────────────────────────────────────────────────

export interface TradeIn {
  ticker: string;
  market?: string;
  trade_type: "BUY" | "SELL";
  quantity: number;
  price: number;
  currency: "KRW" | "USD";
  traded_at: string;
  fee?: number;
  note?: string;
}

export interface TradeOut extends TradeIn {
  id: number;
  created_at: string;
}

// ── M8 Performance ─────────────────────────────────────────────────────────

export interface BenchmarkStats {
  return_pct: number;
  correlation: number;
}

export interface PerformanceChartPoint {
  date: string;
  portfolio: number;
  kospi: number;
  sp500: number;
}

export interface PerformanceData {
  sharpe: number;
  mdd: number;
  total_return: number;
  annualized_return: number;
  benchmark: Record<string, BenchmarkStats>;
  chart: PerformanceChartPoint[];
}

// ── M8 Rebalancing ─────────────────────────────────────────────────────────

export interface RebalancingRow {
  ticker: string;
  name: string;
  current_weight: number;
  target_weight: number | null;
  diff_weight: number | null;
  action: "BUY" | "SELL" | "HOLD" | "NO_TARGET";
  amount_krw: number;
}
