import type {
  BacktestRunIn, BacktestRunOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const holdingsApi = {
  list: () => request<HoldingOut[]>("/api/holdings"),
  upsert: (ticker: string, body: HoldingIn) =>
    request<HoldingOut>(`/api/holdings/${ticker}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (ticker: string) =>
    request<{ ok: boolean }>(`/api/holdings/${ticker}`, { method: "DELETE" }),
  getCash: () => request<{ cash_krw: number; cash_usd: number }>("/api/holdings/cash"),
  updateCash: (body: CashUpdate) =>
    request<{ ok: boolean }>("/api/holdings/cash", { method: "PUT", body: JSON.stringify(body) }),
  lookup: (ticker: string, market?: string) => {
    const params = market ? `?market=${encodeURIComponent(market)}` : "";
    return request<TickerLookupOut>(`/api/holdings/lookup/${encodeURIComponent(ticker)}${params}`);
  },
  search: (q: string) =>
    request<TickerSearchHit[]>(`/api/holdings/search?q=${encodeURIComponent(q)}`),
};

export const portfolioApi = {
  current: () => request<PortfolioSnapshot>("/api/portfolio/current"),
  history: (limit = 8640) =>
    request<SnapshotHistory[]>(`/api/portfolio/history?limit=${limit}`),
  events: () => request<EventOut[]>("/api/portfolio/events"),
  addEvent: (body: Omit<EventOut, "id">) =>
    request<EventOut>("/api/portfolio/events", { method: "POST", body: JSON.stringify(body) }),
  deleteEvent: (id: number) =>
    request<{ ok: boolean }>(`/api/portfolio/events/${id}`, { method: "DELETE" }),
};

export const backtestApi = {
  strategies: () => request<StrategyDef[]>("/api/backtest/strategies"),
  run: (body: BacktestRunIn) =>
    request<BacktestRunOut>("/api/backtest/run", { method: "POST", body: JSON.stringify(body) }),
};
