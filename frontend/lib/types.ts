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

export interface TickerDataStatus {
  ticker: string;
  data_type: string;
  source: string;
  min_date: string | null;
  max_date: string | null;
  last_fetched_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  coverage_json: Record<string, unknown>;
}

export interface TickerOverview {
  ticker: string;
  profile: Record<string, unknown> | null;
  fundamentals: Record<string, unknown> | null;
  status: TickerDataStatus[];
}

export interface TickerHydrate {
  ticker: string;
  scopes: string[];
  warnings: string[];
  status: TickerDataStatus[];
}

export interface HoldingOut extends HoldingIn {
  ticker: string;
  updated_at: string;
  sources: Array<{
    source: string;
    account_id: string;
    ticker: string;
    name: string;
    currency: string;
    quantity: number;
    avg_price: number;
    sector?: string | null;
    market?: string | null;
    excluded_from_portfolio?: boolean | null;
    updated_at: string;
  }>;
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

export interface HoldingSourceMetaUpdate {
  source: string;
  account_id?: string;
  name?: string;
  sector?: string;
  excluded_from_portfolio?: boolean;
}

export interface CashOut {
  cash_krw: number;
  cash_usd: number;
  total_cash_krw?: number;
  total_cash_usd?: number;
  sources?: Array<{
    source: string;
    cash_krw: number;
    cash_usd: number;
  }>;
}

export interface JobRun {
  id: number;
  job_id: string;
  status: "running" | "success" | "failed" | "skipped" | string;
  trigger_type: "schedule" | "manual" | string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  message: string | null;
  error: string | null;
  meta_json: Record<string, unknown>;
}

export interface JobOut {
  id: string;
  name: string;
  category: string;
  schedule: string;
  description: string;
  bootstrap: boolean;
  bootstrap_description: string | null;
  latest_run: JobRun | null;
}

export interface GoldenCrossActive {
  ticker: string;
  market: "KR" | "US" | string;
  group_name: "KOSPI" | "KOSDAQ" | "US" | string | null;
  name: string | null;
  first_detected_at: string;
  last_sent_at: string | null;
  day_count: number;
  already_sent_today: boolean;
}

export interface GoldenCrossHistory {
  id: number;
  ticker: string;
  market: "KR" | "US" | string;
  group_name: "KOSPI" | "KOSDAQ" | "US" | string | null;
  name: string | null;
  status: "NEW" | "MAINTAINED" | "EXPIRED" | "BROKEN" | string;
  day_count: number | null;
  cross_start_date: string | null;
  checked_at: string;
  close: number | null;
  ema5: number | null;
  ema20: number | null;
  ema60: number | null;
  reason: string | null;
}

export interface GoldenCrossOut {
  active: GoldenCrossActive[];
  history: GoldenCrossHistory[];
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
  market?: string;
}

export interface TickerPerformance {
  ticker: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  avg_volume20: number | null;
  perf_1w: number | null;
  perf_1m: number | null;
  perf_6m: number | null;
  perf_ytd: number | null;
  ma20: number | null;
  ma50: number | null;
  ma200: number | null;
  price_vs_ma20: number | null;
  price_vs_ma50: number | null;
  price_vs_ma200: number | null;
  day_low: number | null;
  day_high: number | null;
  range_52w_low: number | null;
  range_52w_high: number | null;
}

export interface PortfolioAnalyticsRow extends TickerPerformance {
  quantity: number;
  avg_price: number;
  currency: string;
  market_value_krw: number | null;
  return_pct: number | null;
  weight_pct: number | null;
}

export interface Watchlist {
  id: number;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface WatchlistItem extends TickerPerformance {
  watchlist_id: number;
  universe: string;
  memo: string | null;
  growth_composite: number | null;
  timing_status: GrowthTiming["status"] | null;
  timing_aligned: boolean | null;
  timing_pullback_stage: GrowthTiming["pullback_stage"] | null;
  timing_volume_level: GrowthTiming["volume_level"] | null;
  timing_volume_ratio: number | null;
  timing_rsi_level: GrowthTiming["rsi_level"] | null;
  timing_rsi14: number | null;
}

export interface WatchlistMembership extends Watchlist {
  universe: string;
  memo: string | null;
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
  cash_krw: number;
  total_equity_usd: number;
  total_with_cash_usd: number;
  cash_usd: number;
  usdkrw: number;
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

export interface GrowthScore {
  ticker: string;
  universe: string;
  as_of: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  pct_growth: number | null;
  pct_profitability: number | null;
  pct_cashflow: number | null;
  pct_stability: number | null;
  growth_composite: number | null;
  rank: number | null;
  rank_1w_ago: number | null;
  rank_1m_ago: number | null;
  delta_1w: number | null;
  delta_1m: number | null;
  raw_roic: number | null;
  raw_oper_margin: number | null;
  raw_current_ratio: number | null;
  raw_sales_growth: number | null;
  raw_market_cap_usd_m: number | null;
  raw_market_cap_krw: number | null;
  raw_fwd_rev_growth: number | null;
  raw_fwd_eps_growth: number | null;
  raw_peg: number | null;
  raw_fwd_pe: number | null;
  raw_psr: number | null;
  data_coverage: { factor_count?: number; missing_factors?: string[] } | null;
  timing_status: GrowthTiming["status"] | null;
  timing_aligned: boolean | null;
  timing_pullback: boolean | null;
  timing_pullback_stage: GrowthTiming["pullback_stage"] | null;
  timing_volume_explosion: boolean | null;
  timing_volume_level: GrowthTiming["volume_level"] | null;
  timing_volume_direction: GrowthTiming["volume_direction"] | null;
  timing_rsi_level: GrowthTiming["rsi_level"] | null;
  timing_downgrade_reasons: TimingReason[];
}

export interface GrowthWatchlistStatus {
  ticker: string;
  universe: string;
  in_watchlist: boolean;
}

export interface ConsensusAttempt {
  source: "FMP" | "FINVIZ" | "STOCKANALYSIS" | "KIS";
  status: string;
}

export interface GrowthValuation {
  ticker: string;
  score_status: "ok" | "missing" | string | null;
  score_message: string | null;
  valuation_source: "BATCH" | "FINVIZ" | string | null;
  valuation_as_of: string | null;
  valuation_stale: boolean;
  missing_reasons: string[];
  peg: number | null;
  forward_pe: number | null;
  psr: number | null;
  forward_eps: number | null;
  forward_revenue_growth: number | null;
  forward_eps_growth: number | null;
  consensus_status: "ok" | "missing" | "no_data" | "rate_limited" | "subscription_limited" | "temporary_error" | "missing_key";
  consensus_message: string | null;
  consensus_source: "FMP" | "FINVIZ" | "STOCKANALYSIS" | "KIS" | null;
  retry_after: string | null;
  current_price: number | null;
  target_mean: number | null;
  target_median: number | null;
  target_low: number | null;
  target_high: number | null;
  upside_pct: number | null;
  analyst_count: number | null;
  consensus_as_of: string | null;
  fallback_used: boolean;
  consensus_attempts: ConsensusAttempt[];
}

export interface GrowthHydrate {
  ticker: string;
  universe: string;
  warnings: string[];
  timing_status: GrowthTiming["status"] | null;
  timing_rows: number | null;
  volume_level: GrowthTiming["volume_level"] | null;
  volume_direction: GrowthTiming["volume_direction"] | null;
  rsi14: number | null;
  rsi_level: GrowthTiming["rsi_level"] | null;
  positive_reasons: TimingReason[];
  warning_reasons: TimingReason[];
  downgrade_reasons: TimingReason[];
}

export interface TimingReason {
  code: string;
  message: string;
  severity: "positive" | "warning" | "downgrade" | string;
}

export interface GrowthTiming {
  status: "suitable" | "watch" | "unsuitable" | "unknown";
  reason?: string | null;
  rows?: number | null;
  aligned?: boolean | null;
  pullback?: boolean | null;
  pullback_stage?: "approach" | "lower" | "breakdown" | "none" | null;
  volume_explosion?: boolean | null;
  volume_ratio?: number | null;
  volume_level?: "quiet" | "normal" | "increased" | "strong" | "explosive" | null;
  volume_direction?: "bullish" | "bearish" | "flat" | null;
  recent_bearish_volume_spike?: boolean | null;
  rsi14?: number | null;
  rsi_level?: "oversold" | "neutral" | "overheated" | "extreme_overheated" | null;
  positive_reasons?: TimingReason[];
  warning_reasons?: TimingReason[];
  downgrade_reasons?: TimingReason[];
  close?: number | null;
  ema20?: number | null;
  ema50?: number | null;
  ema200?: number | null;
  volume?: number | null;
  avg_volume20?: number | null;
  data_sufficiency?: {
    price?: boolean;
    ema20?: boolean;
    ema50?: boolean;
    ema200?: boolean;
    rsi?: boolean;
    volume?: boolean;
  } | null;
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
  updated_at: string
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
  source: string;
  external_id?: string | null;
  created_at: string;
}

export interface TradeImportRow extends TradeIn {
  row_id: string;
  name?: string | null;
  raw_symbol?: string | null;
  needs_mapping: boolean;
}

export interface TradeImportPreview {
  rows: TradeImportRow[];
  errors: string[];
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

export interface FinancialDataPoint {
  year?: string;
  period?: string;
  period_end?: string;
  value: number;
  is_estimate: boolean;
}

export interface QuarterlyFinancialDataPoint {
  period: string;
  value: number;
  is_estimate: boolean;
}

export interface FinancialMetrics {
  market_cap_m: number | null;
  trailing_pe: number | null;
  forward_pe: number | null;
  peg: number | null;
  price_to_sales: number | null;
}

export interface FinancialsData {
  revenue: FinancialDataPoint[];
  eps: FinancialDataPoint[];
  roe: FinancialDataPoint[];
  latest_report_date: string | null;
  metrics: FinancialMetrics;
  quarterly: {
    revenue: QuarterlyFinancialDataPoint[];
    eps: QuarterlyFinancialDataPoint[];
    roe: QuarterlyFinancialDataPoint[];
  };
}

export interface OhlcvPoint {
  date: string;
  close: number;
}

export interface EmaPoint {
  date: string;
  value: number;
}

export interface QuarterlyEpsPoint {
  period: string;
  date: string;
  eps: number;
  is_estimate: boolean;
}

export interface PriceChartData {
  ohlcv: OhlcvPoint[];
  ema: {
    e5: EmaPoint[];
    e20: EmaPoint[];
    e60: EmaPoint[];
  };
  quarterly_eps: QuarterlyEpsPoint[];
}
