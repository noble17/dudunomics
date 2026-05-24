export interface HoldingIn {
  name: string;
  currency: "KRW" | "USD";
  quantity: number;
  avg_price: number;
}

export interface HoldingOut extends HoldingIn {
  ticker: string;
  updated_at: string;
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
    min: number;
    max: number;
  }>;
}

export interface BacktestRunIn {
  ticker: string;
  strategy: string;
  params: Record<string, number>;
  period_start: string;
  period_end: string;
}

export interface BacktestRunOut {
  id: number;
  ticker: string;
  strategy: string;
  params: Record<string, number>;
  period_start: string;
  period_end: string;
  total_return: number;
  mdd: number;
  sharpe: number;
  equity_curve: Array<{ ts: string; equity: number }>;
  created_at: string;
}
