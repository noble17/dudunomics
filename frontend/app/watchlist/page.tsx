"use client";

import { useMemo, useRef, useState } from "react";
import useSWR from "swr";

import { PerformanceTable } from "@/components/performance/performance-table";
import { TickerDetail } from "@/components/stocks/ticker-detail";
import { Button } from "@/components/ui/button";
import { holdingsApi, watchlistsApi } from "@/lib/api";
import type { TickerSearchHit, WatchlistItem } from "@/lib/types";

export default function WatchlistPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newListName, setNewListName] = useState("");
  const [editListId, setEditListId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<TickerSearchHit[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const detailRef = useRef<HTMLElement | null>(null);

  const { data: lists = [], mutate: mutateLists } = useSWR("/api/watchlists", watchlistsApi.list);
  const activeId = selectedId ?? lists[0]?.id ?? null;
  const { data: items = [], isLoading: itemsLoading, mutate: mutateItems } = useSWR(
    activeId ? `/api/watchlists/${activeId}/items` : null,
    () => watchlistsApi.items(activeId!),
    { refreshInterval: 60_000 },
  );

  const activeList = useMemo(() => lists.find((list) => list.id === activeId), [activeId, lists]);
  const formName = editListId === activeId ? editName : activeList?.name ?? "";
  const formDescription = editListId === activeId ? editDescription : activeList?.description ?? "";
  const selectedItem = useMemo(
    () => items.find((item) => item.ticker === selectedTicker) ?? items[0] ?? null,
    [items, selectedTicker],
  );
  const detailTicker = selectedItem?.ticker ?? null;
  const detailUniverse = selectedItem?.universe ?? "sp500";

  const createList = async () => {
    const name = newListName.trim();
    if (!name) return;
    const created = await watchlistsApi.create(name);
    setSelectedId(created.id);
    setNewListName("");
    await mutateLists();
  };

  const updateList = async () => {
    if (!activeId) return;
    const name = formName.trim();
    if (!name) return;
    await watchlistsApi.update(activeId, {
      name,
      description: formDescription.trim() || null,
    });
    setEditListId(null);
    setMessage(`${name} Watchlist를 저장했습니다.`);
    await mutateLists();
  };

  const deleteList = async () => {
    if (!activeId) return;
    await watchlistsApi.delete(activeId);
    setSelectedId(null);
    setSelectedTicker(null);
    setMessage("Watchlist를 삭제했습니다.");
    await mutateLists();
  };

  const search = async () => {
    const value = query.trim();
    if (!value) return;
    setHits(await holdingsApi.search(value));
  };

  const addTicker = async (hit: TickerSearchHit) => {
    if (!activeId) return;
    await watchlistsApi.addItem(activeId, hit.ticker, {
      name: hit.name,
      universe: inferUniverse(hit.ticker),
    });
    setSelectedTicker(hit.ticker);
    setMessage(`${hit.ticker}를 ${activeList?.name ?? "Watchlist"}에 추가했습니다.`);
    setQuery("");
    setHits([]);
    await Promise.all([mutateItems(), mutateLists()]);
  };

  const removeTicker = async (row: WatchlistItem) => {
    await watchlistsApi.removeItem(row.watchlist_id, row.ticker, row.universe);
    if (selectedTicker === row.ticker) setSelectedTicker(null);
    setMessage(`${row.ticker}를 Watchlist에서 제거했습니다.`);
    await Promise.all([mutateItems(), mutateLists()]);
  };

  const toggleTimingAlert = async (row: WatchlistItem, enabled: boolean) => {
    await watchlistsApi.updateItem(row.watchlist_id, row.ticker, {
      name: row.name,
      universe: row.universe,
      memo: row.memo ?? undefined,
      timing_alert_enabled: enabled,
    });
    setMessage(`${row.ticker} TIMING CHECK Telegram 알림을 ${enabled ? "켰습니다" : "껐습니다"}.`);
    await mutateItems();
  };

  const selectTicker = (ticker: string) => {
    setSelectedTicker(ticker);
    window.setTimeout(() => {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };

  return (
    <div className="space-y-5">
      <header className="rounded-xl border border-border bg-card p-5">
        <p className="font-data text-[10px] tracking-[0.24em] text-primary">WATCHLIST</p>
        <h1 className="mt-2 font-heading text-2xl font-medium tracking-tight">관심종목</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          여러 Watchlist에 종목을 담고, Performance View로 기간 수익률과 이평선 위치를 비교합니다.
        </p>
      </header>

      <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl border border-border bg-card p-4">
          <div className="space-y-2">
            {lists.map((list) => (
              <button
                key={list.id}
                type="button"
                onClick={() => setSelectedId(list.id)}
                className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-sm ${
                  activeId === list.id ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground"
                }`}
              >
                <span>{list.name}</span>
                <span className="font-data text-xs">{list.item_count}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <input
              value={newListName}
              onChange={(event) => setNewListName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void createList();
              }}
              placeholder="새 Watchlist"
              className="min-w-0 flex-1 rounded border border-border bg-background px-3 py-2 text-sm"
            />
            <Button type="button" onClick={createList}>추가</Button>
          </div>
        </aside>

        <main className="min-w-0 space-y-4">
          <section className="rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{activeList?.name ?? "Watchlist"}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  종목을 검색해 현재 Watchlist에 추가하고, 선택 종목은 아래에서 매수 검증합니다.
                </p>
              </div>
              <div className="flex min-w-[320px] gap-2">
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void search();
                  }}
                  placeholder="예: MU, SNDK, 삼성전자"
                  className="min-w-0 flex-1 rounded border border-border bg-background px-3 py-2 text-sm"
                />
                <Button type="button" onClick={search}>검색</Button>
              </div>
            </div>
            {hits.length > 0 && (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {hits.slice(0, 8).map((hit) => (
                  <button
                    key={`${hit.ticker}-${hit.exchange}`}
                    type="button"
                    onClick={() => addTicker(hit)}
                    className="rounded border border-border px-3 py-2 text-left hover:border-primary"
                  >
                    <p className="font-data text-sm text-primary">{hit.ticker}</p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{hit.name}</p>
                  </button>
                ))}
              </div>
            )}
          </section>

          {activeList && (
            <section className="rounded-xl border border-border bg-card p-4">
              <div className="grid gap-3 md:grid-cols-[1fr_1.4fr_auto_auto]">
                <input
                  value={formName}
                  onChange={(event) => {
                    setEditListId(activeId);
                    setEditName(event.target.value);
                    setEditDescription(formDescription);
                  }}
                  placeholder="Watchlist 이름"
                  className="min-w-0 rounded border border-border bg-background px-3 py-2 text-sm"
                />
                <input
                  value={formDescription}
                  onChange={(event) => {
                    setEditListId(activeId);
                    setEditName(formName);
                    setEditDescription(event.target.value);
                  }}
                  placeholder="설명 또는 투자 아이디어"
                  className="min-w-0 rounded border border-border bg-background px-3 py-2 text-sm"
                />
                <Button type="button" onClick={updateList}>저장</Button>
                <Button type="button" variant="outline" onClick={deleteList}>삭제</Button>
              </div>
            </section>
          )}

          {message && <p className="rounded border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">{message}</p>}

          <section className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
            <div className="border-b border-border px-5 py-3">
              <p className="text-sm font-medium">Performance View</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Vs MA 컬럼은 현재가 대비율과 실제 MA 값을 함께 표시합니다.
              </p>
            </div>
            {itemsLoading ? (
              <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
                Watchlist 종목을 불러오는 중입니다.
              </div>
            ) : items.length > 0 ? (
              <PerformanceTable
                rows={items}
                mode="watchlist"
                selectedTicker={detailTicker}
                onSelect={selectTicker}
                onRemove={removeTicker}
                onToggleTimingAlert={toggleTimingAlert}
              />
            ) : (
              <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
                아직 담긴 종목이 없습니다. 위 검색창에서 관심 종목을 추가하세요.
              </div>
            )}
          </section>

          {detailTicker && (
            <section ref={detailRef} className="scroll-mt-20 min-w-0 space-y-4">
              <TickerDetail
                key={`${detailTicker}-${detailUniverse}`}
                ticker={detailTicker}
                universe={detailUniverse}
                name={selectedItem?.name}
                compact
              />
            </section>
          )}
        </main>
      </section>
    </div>
  );
}

function inferUniverse(ticker: string) {
  if (ticker.endsWith(".KS")) return "kospi200";
  if (ticker.endsWith(".KQ")) return "kosdaq150";
  return "sp500";
}
