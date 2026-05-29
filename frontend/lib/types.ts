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
}
