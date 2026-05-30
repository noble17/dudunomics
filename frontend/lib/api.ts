import type {
  BacktestRunIn, BacktestRunOut, CandlesOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
  WorkspaceLayout,
  QuotesOut,
  NewsOut, AISummaryOut, ChatMessage,
  AlertCondition, AlertEvent, AlertIn,
  TradeIn, TradeOut, PerformanceData, RebalancingRow,
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

export const workspaceApi = {
  get: (name = "default") =>
    request<{ layout: WorkspaceLayout; name: string }>(`/api/workspace?name=${name}`),
  save: (layout: WorkspaceLayout, name = "default") =>
    request<{ ok: boolean }>("/api/workspace", {
      method: "PUT",
      body: JSON.stringify({ layout, name }),
    }),
};

export const quotesApi = {
  get: () => request<QuotesOut>("/api/quotes"),
};

export const candlesApi = {
  get: (ticker: string, period: string, indicators = false) =>
    request<CandlesOut>(
      `/api/candles?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}${indicators ? "&indicators=true" : ""}`
    ),
};

export const alertsApi = {
  list: () => request<AlertCondition[]>("/api/alerts"),
  create: (body: AlertIn) =>
    request<AlertCondition>("/api/alerts", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number) =>
    fetch(`/api/alerts/${id}`, { method: "DELETE", credentials: "include" }),
  events: () => request<AlertEvent[]>("/api/alerts/events"),
  unread: () => request<AlertEvent[]>("/api/alerts/events/unread"),
  markRead: () =>
    fetch("/api/alerts/events/read", { method: "POST", credentials: "include" }),
};

export const newsApi = {
  get: (ticker: string, limit = 10): Promise<NewsOut> =>
    request<NewsOut>(`/api/news?ticker=${encodeURIComponent(ticker)}&limit=${limit}`),
};

export const aiApi = {
  summary: (ticker: string): Promise<AISummaryOut> =>
    request<AISummaryOut>(`/api/ai/summary?ticker=${encodeURIComponent(ticker)}`),

  streamChat: async (
    messages: ChatMessage[],
    ticker: string | null,
    onChunk: (text: string) => void,
  ): Promise<void> => {
    const res = await fetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ messages, ticker }),
    });
    if (!res.ok || !res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          onChunk(line.slice(6));
        }
      }
    }
  },
};

export const tradesApi = {
  list: (ticker?: string): Promise<TradeOut[]> =>
    request<TradeOut[]>(`/api/trades${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`),
  create: (body: TradeIn): Promise<TradeOut> =>
    request<TradeOut>("/api/trades", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number): Promise<{ ok: boolean }> =>
    request<{ ok: boolean }>(`/api/trades/${id}`, { method: "DELETE" }),
};

export const performanceApi = {
  get: (period = "6m"): Promise<PerformanceData> =>
    request<PerformanceData>(`/api/portfolio/performance?period=${period}`),
};

export const rebalancingApi = {
  get: (): Promise<RebalancingRow[]> =>
    request<RebalancingRow[]>("/api/portfolio/rebalancing"),
  setTargetWeight: (ticker: string, target_weight: number | null) =>
    request<{ ok: boolean; total_target_weight: number; over_100: boolean }>(
      `/api/holdings/${ticker}`,
      { method: "PATCH", body: JSON.stringify({ target_weight }) }
    ),
};
