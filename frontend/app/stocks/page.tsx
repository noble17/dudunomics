"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";

import { TickerDetail } from "@/components/stocks/ticker-detail";
import { Button } from "@/components/ui/button";
import { MarketStrip } from "@/components/market/market-strip";
import { holdingsApi, watchlistsApi } from "@/lib/api";
import type { TickerSearchHit } from "@/lib/types";

export default function StocksPage() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<TickerSearchHit[]>([]);
  const [selected, setSelected] = useState<TickerSearchHit | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [targetWatchlistId, setTargetWatchlistId] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const { data: watchlists = [], mutate: mutateWatchlists } = useSWR("/api/watchlists", watchlistsApi.list);
  const { data: memberships = [], mutate: mutateMemberships } = useSWR(
    selected ? `/api/watchlists/memberships/${selected.ticker}` : null,
    () => watchlistsApi.memberships(selected!.ticker),
  );
  const selectedUniverse = useMemo(() => inferUniverse(selected?.ticker ?? ""), [selected]);
  const activeWatchlistId = targetWatchlistId ?? watchlists[0]?.id ?? null;
  const activeAlreadyIncluded = Boolean(activeWatchlistId && memberships.some((watchlist) => watchlist.id === activeWatchlistId));

  const search = async () => {
    const value = query.trim();
    if (!value) return;
    const result = await holdingsApi.search(value);
    setHits(result);
    setMessage(result.length ? null : `"${value}" 검색 결과가 없습니다.`);
    if (result.length === 1) setSelected(result[0]);
  };

  const saveToWatchlist = async () => {
    if (!selected || !activeWatchlistId) return;
    setIsSaving(true);
    try {
      await watchlistsApi.addItem(activeWatchlistId, selected.ticker, {
        name: selected.name,
        universe: selectedUniverse,
      });
      const targetName = watchlists.find((list) => list.id === activeWatchlistId)?.name ?? "Watchlist";
      setMessage(`${selected.ticker}를 ${targetName}에 저장했습니다.`);
      await Promise.all([mutateWatchlists(), mutateMemberships()]);
    } catch (error) {
      const errorText = error instanceof Error ? error.message : "알 수 없는 오류";
      setMessage(`Watchlist 저장 중 오류가 발생했습니다: ${errorText}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <header className="rounded-xl border border-border bg-card p-5">
        <p className="font-data text-[10px] tracking-[0.24em] text-primary">STOCK HUB</p>
        <h1 className="mt-2 font-heading text-2xl font-medium tracking-tight">종목검색</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          종목을 먼저 조회하고, 공통 데이터 기반 차트·밸류에이션·매수 타이밍을 한 화면에서 확인합니다.
          여기서 Watchlist, 좋은종목찾기, 백테스트로 자연스럽게 이어지는 허브로 키울 예정입니다.
        </p>
      </header>
      <MarketStrip />

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[280px] flex-1">
            <label className="text-xs text-muted-foreground" htmlFor="ticker-search">
              Symbol 또는 회사명
            </label>
            <input
              id="ticker-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void search();
              }}
              placeholder="예: MU, SNDK, 삼성전자"
              className="mt-2 w-full rounded border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            />
          </div>
          <Button type="button" onClick={search}>검색</Button>
        </div>

        {message && <p className="mt-3 text-xs text-muted-foreground">{message}</p>}

        {hits.length > 0 && (
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {hits.slice(0, 12).map((hit) => (
              <button
                key={`${hit.ticker}-${hit.exchange}`}
                type="button"
                onClick={() => setSelected(hit)}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  selected?.ticker === hit.ticker
                    ? "border-primary bg-primary/10"
                    : "border-border bg-background/40 hover:border-primary/60"
                }`}
              >
                <p className="font-data text-sm text-primary">{hit.ticker}</p>
                <p className="mt-1 truncate text-xs text-muted-foreground">{hit.name}</p>
                {hit.exchange && <p className="mt-1 text-[11px] text-muted-foreground">{hit.exchange}</p>}
              </button>
            ))}
          </div>
        )}
      </section>

      {selected ? (
        <section className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-medium">선택 종목 액션</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {selected.ticker}를 관심 Watchlist에 저장해두고 나중에 비교할 수 있습니다.
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-muted-foreground">현재 포함:</span>
                  {memberships.length ? (
                    memberships.map((watchlist) => (
                      <span
                        key={watchlist.id}
                        className="rounded border border-primary/40 bg-primary/10 px-2 py-1 text-primary"
                      >
                        {watchlist.name}
                      </span>
                    ))
                  ) : (
                    <span className="rounded border border-border bg-background px-2 py-1 text-muted-foreground">
                      아직 없음
                    </span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={activeWatchlistId ?? ""}
                  onChange={(event) => setTargetWatchlistId(Number(event.target.value))}
                  className="h-8 rounded border border-border bg-background px-3 text-sm"
                  disabled={!watchlists.length}
                >
                  {watchlists.map((watchlist) => (
                    <option key={watchlist.id} value={watchlist.id}>
                      {watchlist.name}
                      {memberships.some((membership) => membership.id === watchlist.id)
                        ? " (포함됨)"
                        : ` (${watchlist.item_count})`}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  onClick={saveToWatchlist}
                  disabled={!activeWatchlistId || isSaving}
                >
                  {isSaving ? "저장 중" : activeAlreadyIncluded ? "Watchlist 정보 갱신" : "Watchlist 저장"}
                </Button>
              </div>
            </div>
            {!watchlists.length && (
              <p className="mt-3 text-xs text-muted-foreground">
                아직 Watchlist가 없습니다. 관심종목 화면에서 Watchlist를 먼저 만들어 주세요.
              </p>
            )}
          </div>
          <TickerDetail ticker={selected.ticker} universe={selectedUniverse} name={selected.name} />
        </section>
      ) : (
        <section className="rounded-xl border border-dashed border-border bg-card/60 p-8 text-center">
          <p className="text-sm text-muted-foreground">
            관심 있는 종목을 검색하면 가격 차트와 매수 검증 카드가 이곳에 표시됩니다.
          </p>
        </section>
      )}
    </div>
  );
}

function inferUniverse(ticker: string) {
  if (ticker.endsWith(".KS")) return "kospi200";
  if (ticker.endsWith(".KQ")) return "kosdaq150";
  return "sp500";
}
