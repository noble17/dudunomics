"use client";

import { useMemo, useRef, useState } from "react";
import useSWR from "swr";

import { AlertManager } from "@/components/alerts/alert-manager";
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
  const [alertTicker, setAlertTicker] = useState<string | null>(null);
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
    await mutateItems(
      (current = []) => current.map((item) => (
        item.watchlist_id === row.watchlist_id && item.ticker === row.ticker && item.universe === row.universe
          ? { ...item, timing_alert_enabled: enabled }
          : item
      )),
      { revalidate: false },
    );
    try {
      await watchlistsApi.updateItem(row.watchlist_id, row.ticker, {
        name: row.name,
        universe: row.universe,
        memo: row.memo ?? undefined,
        timing_alert_enabled: enabled,
      });
      setMessage(`${row.ticker} TIMING CHECK Telegram 알림을 ${enabled ? "켰습니다" : "껐습니다"}.`);
      await mutateItems();
    } catch {
      await mutateItems(
        (current = []) => current.map((item) => (
          item.watchlist_id === row.watchlist_id && item.ticker === row.ticker && item.universe === row.universe
            ? { ...item, timing_alert_enabled: row.timing_alert_enabled }
            : item
        )),
        { revalidate: false },
      );
      setMessage(`${row.ticker} 알림 설정 저장에 실패했습니다.`);
    }
  };

  const selectTicker = (ticker: string) => {
    setSelectedTicker(ticker);
    window.setTimeout(() => {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };

  const openAlerts = (row: WatchlistItem) => {
    setAlertTicker(row.ticker);
    setSelectedTicker(row.ticker);
    setMessage(`${row.ticker} 조건 알림을 설정할 수 있습니다.`);
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

      <section className="space-y-4">
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium">Watchlist 선택</p>
              <p className="mt-1 text-xs text-muted-foreground">
                목록을 바꾸면 아래 Performance View와 상세 차트가 함께 갱신됩니다.
              </p>
            </div>
            <div className="flex min-w-0 flex-1 flex-wrap gap-2 xl:justify-end">
              {lists.map((list) => (
                <button
                  key={list.id}
                  type="button"
                  onClick={() => setSelectedId(list.id)}
                  className={`flex min-w-[160px] max-w-full items-center justify-between gap-4 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    activeId === list.id
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border text-muted-foreground hover:border-primary/60 hover:text-foreground"
                  }`}
                >
                  <span className="truncate">{list.name}</span>
                  <span className="shrink-0 font-data text-xs">{list.item_count}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 flex max-w-lg gap-2">
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
        </section>

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
                onOpenAlerts={openAlerts}
              />
            ) : (
              <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
                아직 담긴 종목이 없습니다. 위 검색창에서 관심 종목을 추가하세요.
              </div>
            )}
          </section>

          {alertTicker && (
            <section className="rounded-xl border border-primary/25 bg-card p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-data text-[10px] tracking-[0.2em] text-primary">CONDITION ALERT</p>
                  <h2 className="mt-1 text-base font-semibold text-foreground">{alertTicker} 조건 알림</h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    여러 조건을 추가하면 백엔드가 주기적으로 확인하고 충족 시 Telegram으로 보냅니다.
                  </p>
                </div>
                <Button type="button" variant="outline" onClick={() => setAlertTicker(null)}>
                  닫기
                </Button>
              </div>
              <AlertManager ticker={alertTicker} mode="ticker" />
            </section>
          )}

          {detailTicker && (
            <section ref={detailRef} className="scroll-mt-20 min-w-0 space-y-4">
              <div className="sticky top-14 z-20 rounded-xl border border-primary/30 bg-card/95 px-4 py-3 shadow-sm backdrop-blur">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-data text-[10px] tracking-[0.2em] text-primary">SELECTED TICKER</p>
                    <div className="mt-1 flex min-w-0 items-baseline gap-2">
                      <span className="font-heading text-xl font-medium tracking-tight">{detailTicker}</span>
                      {selectedItem?.name && (
                        <span className="truncate text-sm text-muted-foreground">{selectedItem.name}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded-full border border-border bg-background px-2 py-1">
                      {detailUniverse}
                    </span>
                    {selectedItem?.growth_composite != null && (
                      <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-1 text-primary">
                        성장 {selectedItem.growth_composite.toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
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
