import type {
  BacktestRunIn, BacktestRunOut, CandlesOut, CashOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, HoldingSourceMetaUpdate, PortfolioAnalyticsRow, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
  WorkspaceLayout,
  QuotesOut,
  NewsOut, AISummaryOut, ChatMessage,
  AlertCondition, AlertEvent, AlertIn, AlertTemplate, AlertTemplateIn,
  TradeImportPreview, TradeIn, TradeOut, PerformanceData, RebalancingRow,
  FinancialsData, PriceChartData, Watchlist, WatchlistItem, WatchlistMembership,
  GrowthScore, GrowthTiming, GrowthValuation, GrowthWatchlistStatus,
  GrowthHydrate, TickerHydrate, TickerOverview,
  JobOut, JobRun, GoldenCrossOut,
  CandidateScore,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = init?.body instanceof FormData
    ? init?.headers
    : { "Content-Type": "application/json", ...init?.headers };
  const res = await fetch(path, {
    headers,
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
  updateSourceMeta: (ticker: string, body: HoldingSourceMetaUpdate) =>
    request<HoldingOut>(`/api/holdings/${ticker}/source-meta`, { method: "PATCH", body: JSON.stringify(body) }),
  getCash: () => request<CashOut>("/api/holdings/cash"),
  updateCash: (body: CashUpdate) =>
    request<{ ok: boolean }>("/api/holdings/cash", { method: "PUT", body: JSON.stringify(body) }),
  lookup: (ticker: string, market?: string) => {
    const params = market ? `?market=${encodeURIComponent(market)}` : "";
    return request<TickerLookupOut>(`/api/holdings/lookup/${encodeURIComponent(ticker)}${params}`);
  },
  search: (q: string) =>
    request<TickerSearchHit[]>(`/api/holdings/search?q=${encodeURIComponent(q)}`),
  syncFromKis: () =>
    request<{ added: number; updated: number; errors: string[] }>(
      "/api/holdings/sync-from-kis",
      { method: "POST" }
    ),
  syncFromToss: () =>
    request<{ added: number; updated: number; deleted: number; errors: string[] }>(
      "/api/holdings/sync-from-toss",
      { method: "POST" }
    ),
};

export const jobsApi = {
  list: () => request<JobOut[]>("/api/jobs"),
  runs: (jobId: string, limit = 50) =>
    request<JobRun[]>(`/api/jobs/${encodeURIComponent(jobId)}/runs?limit=${limit}`),
  run: (jobId: string) =>
    request<{ status: string; job_id: string }>(
      `/api/jobs/${encodeURIComponent(jobId)}/run`,
      { method: "POST" },
    ),
  runBootstrap: () =>
    request<{ status: string; job_ids: string[] }>("/api/jobs/bootstrap/run", { method: "POST" }),
};

export const goldenCrossApi = {
  list: (group = "all", limit = 200) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (group === "KOSPI" || group === "KOSDAQ" || group === "US") params.set("group_name", group);
    return request<GoldenCrossOut>(`/api/golden-cross?${params.toString()}`);
  },
};

export const candidatesApi = {
  list: (params: {
    region?: string;
    sector?: string;
    status?: string;
    source?: string;
    limit?: number;
    excludeWatchlist?: boolean;
    weights?: Record<string, number>;
    filters?: Record<string, number | boolean | null>;
  } = {}) => {
    const query = new URLSearchParams({
      region: params.region || "all",
      sector: params.sector || "tech",
      status: params.status || "new",
      source: params.source || "all",
      limit: String(params.limit || 50),
      exclude_watchlist: String(params.excludeWatchlist ?? true),
    });
    if (params.weights) {
      for (const [key, value] of Object.entries(params.weights)) {
        query.set(`${key}_weight`, String(value));
      }
    }
    if (params.filters) {
      for (const [key, value] of Object.entries(params.filters)) {
        if (typeof value === "boolean") {
          query.set(key, String(value));
        } else if (value !== null && value !== undefined && Number.isFinite(value)) {
          query.set(key, String(value));
        }
      }
    }
    return request<CandidateScore[]>(`/api/candidates?${query.toString()}`);
  },
  refresh: (region = "all") =>
    request<{ regions: number; rows: number }>(
      `/api/candidates/refresh?region=${encodeURIComponent(region)}`,
      { method: "POST" },
    ),
  updateStatus: (ticker: string, body: { universe_group: string; status: string; memo?: string | null }) =>
    request<{ ok: boolean; ticker: string; status: string }>(
      `/api/candidates/${encodeURIComponent(ticker)}/shortlist`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  addWatchlist: (ticker: string, universeGroup: string) =>
    request<{ ok: boolean; ticker: string; watchlist_id: number; universe: string }>(
      `/api/candidates/${encodeURIComponent(ticker)}/add-watchlist?universe_group=${encodeURIComponent(universeGroup)}`,
      { method: "POST" },
    ),
};

export const portfolioApi = {
  current: () => request<PortfolioSnapshot>("/api/portfolio/current"),
  analytics: () => request<PortfolioAnalyticsRow[]>("/api/portfolio/analytics"),
  history: (bucket = "10m", limit = 400) =>
    request<SnapshotHistory[]>(`/api/portfolio/history?bucket=${bucket}&limit=${limit}`),
  events: () => request<EventOut[]>("/api/portfolio/events"),
  addEvent: (body: Omit<EventOut, "id">) =>
    request<EventOut>("/api/portfolio/events", { method: "POST", body: JSON.stringify(body) }),
  deleteEvent: (id: number) =>
    request<{ ok: boolean }>(`/api/portfolio/events/${id}`, { method: "DELETE" }),
};

export const watchlistsApi = {
  list: () => request<Watchlist[]>("/api/watchlists"),
  create: (name: string) =>
    request<Watchlist>("/api/watchlists", { method: "POST", body: JSON.stringify({ name }) }),
  update: (id: number, body: { name: string; description?: string | null }) =>
    request<Watchlist>(`/api/watchlists/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (id: number) =>
    request<{ ok: boolean }>(`/api/watchlists/${id}`, { method: "DELETE" }),
  items: (id: number) => request<WatchlistItem[]>(`/api/watchlists/${id}/items`),
  memberships: (ticker: string) =>
    request<WatchlistMembership[]>(`/api/watchlists/memberships/${encodeURIComponent(ticker)}`),
  addItem: (id: number, ticker: string, body: { name?: string; universe?: string; memo?: string; timing_alert_enabled?: boolean }) =>
    request<{ ok: boolean; watchlist_id: number; ticker: string; universe: string }>(
      `/api/watchlists/${id}/items/${encodeURIComponent(ticker)}`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  updateItem: (id: number, ticker: string, body: { name?: string; universe?: string; memo?: string; timing_alert_enabled?: boolean }) =>
    request<{ ok: boolean; watchlist_id: number; ticker: string; universe: string }>(
      `/api/watchlists/${id}/items/${encodeURIComponent(ticker)}`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  removeItem: (id: number, ticker: string, universe = "sp500") =>
    request<{ ok: boolean }>(
      `/api/watchlists/${id}/items/${encodeURIComponent(ticker)}?universe=${encodeURIComponent(universe)}`,
      { method: "DELETE" },
    ),
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
  refresh: (universe = "sp500", force = false) =>
    request<{ status: string }>(`/api/screener/refresh?universe=${universe}&force=${force}`, { method: "POST" }),
  status: (universe = "sp500") =>
    request<{ status: string; step: string; done: number; total: number; finished_at: string; latest_as_of: string; is_fresh: boolean }>(`/api/screener/status?universe=${universe}`),
  getNote: (ticker: string) =>
    request<TickerNote | null>(`/api/screener/notes/${ticker}`),
  upsertNote: (ticker: string, body: Omit<TickerNote, "ticker" | "updated_at">) =>
    request<TickerNote>(`/api/screener/notes/${ticker}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  financials: (ticker: string, universe = "sp500") =>
    request<FinancialsData>(`/api/screener/ticker/${ticker}/financials?universe=${universe}`),
  priceChart: (ticker: string) =>
    request<PriceChartData>(`/api/screener/ticker/${ticker}/price-chart`),
};

export const growthApi = {
  scores: (universe = "sp500") =>
    request<GrowthScore[]>(`/api/growth/scores?universe=${universe}`),
  top: (universe = "sp500", sector = "", cap = "", signal = "") => {
    const params = new URLSearchParams({ universe });
    if (sector) params.set("sector", sector);
    if (cap) params.set("cap", cap);
    if (signal) params.set("signal", signal);
    return request<GrowthScore[]>(`/api/growth/top?${params.toString()}`);
  },
  valuation: (ticker: string, universe = "sp500") =>
    request<GrowthValuation>(`/api/growth/ticker/${ticker}/valuation?universe=${universe}`),
  timing: (ticker: string) =>
    request<GrowthTiming>(`/api/growth/ticker/${ticker}/timing`),
  hydrate: (ticker: string, universe = "sp500") =>
    request<GrowthHydrate>(`/api/growth/ticker/${ticker}/hydrate?universe=${universe}`, { method: "POST" }),
  watchlist: (universe = "sp500") =>
    request<GrowthScore[]>(`/api/growth/watchlist?universe=${universe}`),
  watchlistStatus: (ticker: string, universe = "sp500") =>
    request<GrowthWatchlistStatus>(`/api/growth/watchlist/${ticker}?universe=${universe}`),
  addWatchlist: (ticker: string, universe = "sp500") =>
    request<GrowthWatchlistStatus>(`/api/growth/watchlist/${ticker}?universe=${universe}`, { method: "PUT" }),
  removeWatchlist: (ticker: string, universe = "sp500") =>
    request<GrowthWatchlistStatus>(`/api/growth/watchlist/${ticker}?universe=${universe}`, { method: "DELETE" }),
  refresh: (universe = "sp500", force = false) =>
    request<{ status: string; universe: string }>(`/api/growth/refresh?universe=${universe}&force=${force}`, { method: "POST" }),
  status: (universe = "sp500") =>
    request<{ status: string; step: string; done: number; total: number; finished_at: string; latest_as_of: string; is_fresh: boolean }>(`/api/screener/status?universe=${universe}`),
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

export const tickersApi = {
  overview: (ticker: string, universe = "sp500") =>
    request<TickerOverview>(
      `/api/tickers/${encodeURIComponent(ticker)}/overview?universe=${encodeURIComponent(universe)}`
    ),
  hydrate: (ticker: string, scopes = ["ohlcv"]) =>
    request<TickerHydrate>(
      `/api/tickers/${encodeURIComponent(ticker)}/hydrate?${scopes.map((scope) => `scopes=${encodeURIComponent(scope)}`).join("&")}`,
      { method: "POST" },
    ),
};

export const alertsApi = {
  list: () => request<AlertCondition[]>("/api/alerts"),
  create: (body: AlertIn) =>
    request<AlertCondition>("/api/alerts", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number) =>
    fetch(`/api/alerts/${id}`, { method: "DELETE", credentials: "include" }),
  templates: () => request<AlertTemplate[]>("/api/alerts/templates"),
  createTemplate: (body: AlertTemplateIn) =>
    request<AlertTemplate>("/api/alerts/templates", { method: "POST", body: JSON.stringify(body) }),
  updateTemplate: (id: number, body: AlertTemplateIn) =>
    request<AlertTemplate>(`/api/alerts/templates/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteTemplate: (id: number) =>
    fetch(`/api/alerts/templates/${id}`, { method: "DELETE", credentials: "include" }),
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
  previewTossPdf: (file: File): Promise<TradeImportPreview> => {
    const body = new FormData();
    body.append("file", file);
    return request<TradeImportPreview>("/api/trades/import-toss-pdf/preview", { method: "POST", body });
  },
  commitTossPdf: (body: TradeImportPreview): Promise<{ added: number; updated: number; errors: string[] }> =>
    request<{ added: number; updated: number; errors: string[] }>("/api/trades/import-toss-pdf/commit", { method: "POST", body: JSON.stringify(body) }),
  syncFromToss: (): Promise<{ added: number; updated: number; errors: string[] }> =>
    request<{ added: number; updated: number; errors: string[] }>("/api/trades/sync-from-toss", { method: "POST" }),
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

export const fxApi = {
  rate: (pair: string): Promise<{ pair: string; rate: number; ts: string | null }> =>
    request<{ pair: string; rate: number; ts: string | null }>(`/api/fx/${pair.toUpperCase()}`),
};
