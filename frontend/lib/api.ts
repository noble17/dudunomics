import type {
  BacktestRunIn, BacktestRunOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "include",
    ...init,
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    throw new Error("인증이 필요합니다.");
  }
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

export const screenerApi = {
  scores: (universe = "sp500") =>
    request<QuantScore[]>(`/api/screener/scores?universe=${universe}`),
  ticker: (ticker: string, universe = "sp500") =>
    request<QuantScore>(`/api/screener/ticker/${ticker}?universe=${universe}`),
  refresh: (universe = "sp500") =>
    request<{ status: string }>(`/api/screener/refresh?universe=${universe}`, { method: "POST" }),
  status: (universe = "sp500") =>
    request<{ status: string; step: string; done: number; total: number }>(`/api/screener/status?universe=${universe}`),
  getNote: (ticker: string) =>
    request<TickerNote | null>(`/api/screener/notes/${ticker}`),
  upsertNote: (ticker: string, body: Omit<TickerNote, "ticker" | "updated_at">) =>
    request<TickerNote>(`/api/screener/notes/${ticker}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};
