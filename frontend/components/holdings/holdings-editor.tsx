"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { holdingsApi } from "@/lib/api";
import type { HoldingOut, TickerSearchHit } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const KIS_MARKETS = ["KRX", "NASDAQ", "NYSE", "AMEX"];

function makeRowId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `row-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function marketToCurrency(market: string): "KRW" | "USD" {
  return market === "KRX" ? "KRW" : "USD";
}

interface Row {
  id: string;
  ticker: string;
  name: string;
  sector: string;
  market: string;
  currency: "KRW" | "USD";
  quantity: string;
  avg_price: string;
  sourceSummary: string;
  source: string;
  accountId: string;
  excludedFromPortfolio: boolean;
  hasManual: boolean;
  locked: boolean;
  saved: boolean;
  lookupError: boolean;
}

function toRows(h: HoldingOut): Row[] {
  const sources = h.sources ?? [];
  if (sources.length) {
    return sources.map((s) => ({
      id: `${s.source}:${s.account_id}:${s.ticker}`,
      ticker: s.ticker,
      name: s.name,
      sector: s.sector ?? "",
      market: s.market ?? "",
      currency: s.currency as "KRW" | "USD",
      quantity: String(s.quantity),
      avg_price: String(s.avg_price),
      sourceSummary: s.source,
      source: s.source,
      accountId: s.account_id,
      excludedFromPortfolio: Boolean(s.excluded_from_portfolio),
      hasManual: s.source === "manual",
      locked: s.source !== "manual",
      saved: true,
      lookupError: false,
    }));
  }
  return [{
    id: h.ticker,
    ticker: h.ticker,
    name: h.name,
    sector: h.sector ?? "",
    market: (h as HoldingOut & { market?: string }).market ?? "",
    currency: h.currency as "KRW" | "USD",
    quantity: String(h.quantity),
    avg_price: String(h.avg_price),
    sourceSummary: "manual",
    source: "manual",
    accountId: "",
    excludedFromPortfolio: false,
    hasManual: true,
    locked: false,
    saved: true,
    lookupError: false,
  }];
}

interface Props {
  initialHoldings: HoldingOut[];
  initialCashKrw: number;
  initialCashUsd: number;
  cashSources: Array<{ source: string; cash_krw: number; cash_usd: number }>;
  totalCashKrw: number;
  totalCashUsd: number;
  onReload: () => void;
}

export function HoldingsEditor({
  initialHoldings,
  initialCashKrw,
  initialCashUsd,
  cashSources,
  totalCashKrw,
  totalCashUsd,
  onReload,
}: Props) {
  const [rows, setRows] = useState<Row[]>(initialHoldings.flatMap(toRows));
  const [savedTickers, setSavedTickers] = useState<Set<string>>(
    () => new Set(initialHoldings.filter((h) => !h.sources?.length || h.sources.some((s) => s.source === "manual")).map((h) => h.ticker))
  );
  const [cashKrw, setCashKrw] = useState(String(initialCashKrw));
  const [cashUsd, setCashUsd] = useState(String(initialCashUsd));
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState<"Toss" | null>(null);
  const [status, setStatus] = useState("");

  // 검색 콤보박스 상태
  const [searchRowId, setSearchRowId] = useState<string | null>(null);
  const [searchHits, setSearchHits] = useState<TickerSearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null);

  // lookup 중인 row
  const [lookingUp, setLookingUp] = useState<Set<string>>(new Set());

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      {
        id: makeRowId(),
        ticker: "", name: "", sector: "", market: "",
        currency: "KRW", quantity: "0", avg_price: "0",
        sourceSummary: "manual", source: "manual", accountId: "", hasManual: true,
        excludedFromPortfolio: false,
        locked: false,
        saved: false, lookupError: false,
      },
    ]);

  const update = (
    id: string,
    field: keyof Pick<Row, "ticker" | "name" | "sector" | "market" | "currency" | "quantity" | "avg_price">,
    value: string,
  ) =>
    setRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, [field]: value, saved: false, lookupError: false } : r))
    );

  const togglePortfolioVisibility = (id: string) =>
    setRows((prev) =>
      prev.map((r) => (r.id === id && !r.hasManual ? { ...r, excludedFromPortfolio: !r.excludedFromPortfolio, saved: false } : r))
    );

  const remove = async (row: Row) => {
    if (row.ticker && row.saved) await holdingsApi.delete(row.ticker);
    setRows((prev) => prev.filter((r) => r.id !== row.id));
  };

  // 티커 검색 (debounce 300ms)
  const handleTickerChange = useCallback((id: string, value: string, rect?: DOMRect) => {
    update(id, "ticker", value);
    setSearchRowId(id);
    setSearchHits([]);
    if (rect) setDropdownPos({ top: rect.bottom, left: rect.left });

    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (value.trim().length < 2) {
      setSearchRowId(null);
      return;
    }

    setSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const hits = await holdingsApi.search(value.trim());
        setSearchHits(hits);
      } catch {
        setSearchHits([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  }, []);

  // 검색 결과 선택
  const selectSearchHit = (id: string, hit: TickerSearchHit) => {
    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        const market = hit.market || r.market;
        const currency = market ? marketToCurrency(market) : r.currency;
        return {
          ...r,
          ticker: hit.ticker,
          name: hit.name || r.name,
          market,
          currency,
          saved: false,
          lookupError: false,
        };
      })
    );
    setSearchRowId(null);
    setSearchHits([]);
  };

  // 🔍 조회 버튼
  const handleLookup = async (id: string, ticker: string, market?: string) => {
    if (!ticker) return;
    setLookingUp((prev) => new Set(prev).add(id));
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, lookupError: false } : r)));

    try {
      const info = await holdingsApi.lookup(ticker, market || undefined);
      const currency = info.currency === "KRW" ? "KRW" : "USD";
      setRows((prev) =>
        prev.map((r) =>
          r.id === id
            ? { ...r, name: info.name, market: info.market, currency, saved: false, lookupError: false }
            : r
        )
      );
    } catch {
      // 422 need_market — lookupError 표시
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, lookupError: true } : r)));
    } finally {
      setLookingUp((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // 외부 클릭 시 검색 드롭다운 닫기
  useEffect(() => {
    const handler = () => { setSearchRowId(null); setSearchHits([]); };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  useEffect(() => {
    setRows(initialHoldings.flatMap(toRows));
    setSavedTickers(new Set(
      initialHoldings
        .filter((h) => !h.sources?.length || h.sources.some((s) => s.source === "manual"))
        .map((h) => h.ticker)
    ));
    setCashKrw(String(initialCashKrw));
    setCashUsd(String(initialCashUsd));
  }, [initialHoldings, initialCashKrw, initialCashUsd]);

  const save = async () => {
    setSaving(true);
    setStatus("");
    try {
      const existing = [...savedTickers];
      const current = rows.filter((r) => !r.locked && r.hasManual).map((r) => r.ticker).filter(Boolean);
      for (const t of existing) {
        if (!current.includes(t)) await holdingsApi.delete(t);
      }
      for (const row of rows) {
        if (!row.ticker) continue;
        if (!row.hasManual) {
          if (!row.saved) {
            await holdingsApi.updateSourceMeta(row.ticker, {
              source: row.source,
              account_id: row.accountId,
              name: row.name || undefined,
              sector: row.sector,
              excluded_from_portfolio: row.excludedFromPortfolio,
            });
          }
          continue;
        }
        await holdingsApi.upsert(row.ticker, {
          name: row.name || row.ticker,
          sector: row.sector || undefined,
          market: row.market || undefined,
          currency: row.currency,
          quantity: parseFloat(row.quantity) || 0,
          avg_price: parseFloat(row.avg_price) || 0,
        });
      }
      await holdingsApi.updateCash({
        cash_krw: parseFloat(cashKrw) || 0,
        cash_usd: parseFloat(cashUsd) || 0,
      });
      setRows((prev) => prev.map((r) => ({ ...r, saved: true })));
      setSavedTickers(new Set(rows.filter((r) => r.hasManual).map((r) => r.ticker).filter(Boolean)));
      setStatus("저장 완료");
    } catch (e: unknown) {
      setStatus(`오류: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const sync = async () => {
    const provider = "Toss";
    setSyncing(provider);
    setStatus("");
    try {
      const result = await holdingsApi.syncFromToss();
      onReload();
      if (result.errors.length) {
        setStatus(`오류: ${result.errors[0]}`);
      } else {
        setStatus(`${provider} 동기화 완료: 추가 ${result.added}개, 수정 ${result.updated}개, 삭제 ${result.deleted}개`);
      }
    } catch (e: unknown) {
      setStatus(`오류: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSyncing(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 border border-border bg-card p-4">
        <span className="mr-2 text-sm text-muted-foreground">증권사 데이터 가져오기</span>
        <Button variant="outline" onClick={sync} disabled={syncing !== null}>
          {syncing === "Toss" ? "Toss 동기화 중…" : "Toss 가져오기"}
        </Button>
      </div>

      {/* 현금 입력 */}
      <div className="border border-border bg-card p-5">
        <h3 className="mb-4 text-sm font-medium text-muted-foreground">현금 잔고</h3>
        <div className="flex flex-wrap gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">현금 (KRW)</Label>
            <Input value={cashKrw} onChange={(e) => setCashKrw(e.target.value)}
              type="number" className="w-40 font-data" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">현금 (USD)</Label>
            <Input value={cashUsd} onChange={(e) => setCashUsd(e.target.value)}
              type="number" className="w-40 font-data" />
          </div>
          <div className="flex items-end pb-1 font-data text-xs text-muted-foreground">
            총 현금 KRW {Math.round(totalCashKrw).toLocaleString("ko-KR")} · USD {totalCashUsd.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}
            {cashSources.length > 0 ? ` (${cashSources.map((s) => `${s.source}: KRW ${Math.round(s.cash_krw).toLocaleString("ko-KR")}, USD ${s.cash_usd.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}`).join(" / ")})` : ""}
          </div>
        </div>
      </div>

      {/* 모바일 종목 카드 */}
      <div className="space-y-3 md:hidden">
        {rows.map((row) => (
          <div key={row.id} className="border border-border bg-card p-3">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-data text-xs text-muted-foreground">{row.sourceSummary}</p>
                <p className="mt-1 truncate text-sm font-medium text-foreground">
                  {row.name || row.ticker || "새 보유종목"}
                </p>
              </div>
              <span className={`shrink-0 text-xs font-medium ${row.saved ? "text-muted-foreground" : "text-primary"}`}>
                {row.saved ? "저장됨" : "미저장"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5" onClick={(e) => e.stopPropagation()}>
                <Label className="text-xs text-muted-foreground">티커</Label>
                <Input
                  value={row.ticker}
                  onChange={(e) => handleTickerChange(row.id, e.target.value, e.currentTarget.getBoundingClientRect())}
                  onFocus={(e) => {
                    if (row.ticker.length >= 2) {
                      setSearchRowId(row.id);
                      setDropdownPos({ top: e.currentTarget.getBoundingClientRect().bottom, left: e.currentTarget.getBoundingClientRect().left });
                    }
                  }}
                  className="h-9 font-data"
                  placeholder="005930.KS"
                  disabled={row.locked}
                />
                {searchRowId === row.id && (searchHits.length > 0 || searching) && dropdownPos && (
                  <div
                    className="fixed z-50 border border-border bg-card"
                    style={{ top: dropdownPos.top, left: "1rem", right: "1rem" }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {searching && (
                      <div className="px-3 py-2 font-data text-xs text-muted-foreground">검색 중…</div>
                    )}
                    {searchHits.map((hit) => (
                      <button
                        key={hit.ticker}
                        type="button"
                        onClick={() => selectSearchHit(row.id, hit)}
                        className="flex w-full flex-col px-3 py-2 text-left hover:bg-[var(--secondary)]"
                      >
                        <span className="font-data text-xs text-foreground">{hit.ticker}</span>
                        <span className="text-xs text-muted-foreground">{hit.name} · {hit.exchange}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="col-span-2 space-y-1.5">
                <Label className="text-xs text-muted-foreground">종목명</Label>
                <Input value={row.name} onChange={(e) => update(row.id, "name", e.target.value)}
                  className="h-9" placeholder="종목명" />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">시장</Label>
                {row.lookupError ? (
                  <Select
                    value={row.market}
                    disabled={row.locked}
                    onValueChange={(v) => {
                      if (!v) return;
                      update(row.id, "market", v);
                      handleLookup(row.id, row.ticker, v);
                    }}
                  >
                    <SelectTrigger className="h-9 w-full border-primary font-data text-xs">
                      <SelectValue placeholder="시장 선택" />
                    </SelectTrigger>
                    <SelectContent>
                      {KIS_MARKETS.map((m) => (
                        <SelectItem key={m} value={m} className="font-data text-xs">{m}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={row.market}
                    onChange={(e) => update(row.id, "market", e.target.value)}
                    className="h-9 font-data text-xs"
                    placeholder="NASDAQ"
                    disabled={row.locked}
                  />
                )}
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">통화</Label>
                <Select value={row.currency} disabled={row.locked} onValueChange={(v) => { if (v) update(row.id, "currency", v); }}>
                  <SelectTrigger className="h-9 w-full font-data"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="KRW">KRW</SelectItem>
                    <SelectItem value="USD">USD</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">수량</Label>
                <Input value={row.quantity} onChange={(e) => update(row.id, "quantity", e.target.value)}
                  type="number" className="h-9 font-data" disabled={row.locked} />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">평균단가</Label>
                <Input value={row.avg_price} onChange={(e) => update(row.id, "avg_price", e.target.value)}
                  type="number" className="h-9 font-data" disabled={row.locked} />
              </div>

              <div className="col-span-2 space-y-1.5">
                <Label className="text-xs text-muted-foreground">섹터</Label>
                <Input value={row.sector} onChange={(e) => update(row.id, "sector", e.target.value)}
                  className="h-9 font-data text-xs" placeholder="반도체" />
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
              <button
                type="button"
                onClick={() => togglePortfolioVisibility(row.id)}
                disabled={row.hasManual}
                className={`h-8 border px-2 font-data text-[10px] ${
                  row.excludedFromPortfolio
                    ? "border-border text-muted-foreground hover:text-foreground"
                    : "border-primary text-primary"
                } disabled:cursor-not-allowed disabled:border-border disabled:text-muted-foreground`}
                title={row.excludedFromPortfolio ? "포트폴리오에서 숨김" : "포트폴리오에 포함"}
              >
                {row.excludedFromPortfolio ? "숨김" : "포함"}
              </button>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={row.locked || !row.ticker || lookingUp.has(row.id)}
                  onClick={() => handleLookup(row.id, row.ticker, row.market || undefined)}
                  className="h-8 px-2 font-data text-xs text-muted-foreground hover:text-foreground"
                  title="티커 정보 자동 조회"
                >
                  {lookingUp.has(row.id) ? "…" : "조회"}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => remove(row)} disabled={row.locked}
                  className="h-8 text-xs text-error hover:bg-[rgba(221,60,68,0.08)] hover:text-error">삭제</Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 데스크톱 종목 테이블 */}
      <div className="hidden border border-border md:block">
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-[var(--card)]">
            <tr>
              {["티커", "종목명", "섹터", "시장", "통화", "수량", "평균단가", "출처", "포트폴리오", "상태", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-medium text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-border last:border-0 hover:bg-[var(--secondary)]">
                {/* 티커 + 검색 콤보 */}
                <td className="px-4 py-2">
                  <div className="relative" onClick={(e) => e.stopPropagation()}>
                    <Input
                      value={row.ticker}
                      onChange={(e) => handleTickerChange(row.id, e.target.value, e.currentTarget.getBoundingClientRect())}
                      onFocus={(e) => {
                        if (row.ticker.length >= 2) {
                          setSearchRowId(row.id);
                          setDropdownPos({ top: e.currentTarget.getBoundingClientRect().bottom, left: e.currentTarget.getBoundingClientRect().left });
                        }
                      }}
                      className="h-8 w-32 font-data"
                      placeholder="005930.KS"
                      disabled={row.locked}
                    />
                    {/* 검색 드롭다운 — fixed로 렌더링해서 overflow 클리핑 우회 */}
                    {searchRowId === row.id && (searchHits.length > 0 || searching) && dropdownPos && (
                      <div
                        className="fixed z-50 w-64 border border-border bg-card"
                        style={{ top: dropdownPos.top, left: dropdownPos.left }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {searching && (
                          <div className="px-3 py-2 font-data text-xs text-muted-foreground">검색 중…</div>
                        )}
                        {searchHits.map((hit) => (
                          <button
                            key={hit.ticker}
                            type="button"
                            onClick={() => selectSearchHit(row.id, hit)}
                            className="flex w-full flex-col px-3 py-2 text-left hover:bg-[var(--secondary)]"
                          >
                            <span className="font-data text-xs text-foreground">{hit.ticker}</span>
                            <span className="text-xs text-muted-foreground">{hit.name} · {hit.exchange}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </td>

                {/* 종목명 */}
                <td className="px-4 py-2">
                  <Input value={row.name} onChange={(e) => update(row.id, "name", e.target.value)}
                    className="h-8 w-36" placeholder="종목명" />
                </td>

                {/* 섹터 */}
                <td className="px-4 py-2">
                  <Input value={row.sector} onChange={(e) => update(row.id, "sector", e.target.value)}
                    className="h-8 w-24 font-data text-xs" placeholder="반도체" />
                </td>

                {/* 시장 — 정상이면 텍스트, lookupError면 드롭다운 */}
                <td className="px-4 py-2">
                  {row.lookupError ? (
                    <Select
                      value={row.market}
                      disabled={row.locked}
                      onValueChange={(v) => {
                        if (!v) return;
                        update(row.id, "market", v);
                        handleLookup(row.id, row.ticker, v);
                      }}
                    >
                      <SelectTrigger className="h-8 w-28 font-data text-xs border-primary">
                        <SelectValue placeholder="시장 선택" />
                      </SelectTrigger>
                      <SelectContent>
                        {KIS_MARKETS.map((m) => (
                          <SelectItem key={m} value={m} className="font-data text-xs">{m}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      value={row.market}
                      onChange={(e) => update(row.id, "market", e.target.value)}
                      className="h-8 w-24 font-data text-xs"
                      placeholder="NASDAQ"
                      disabled={row.locked}
                    />
                  )}
                </td>

                {/* 통화 */}
                <td className="px-4 py-2">
                  <Select value={row.currency} disabled={row.locked} onValueChange={(v) => { if (v) update(row.id, "currency", v); }}>
                    <SelectTrigger className="h-8 w-20 font-data"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="KRW">KRW</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                    </SelectContent>
                  </Select>
                </td>

                {/* 수량 */}
                <td className="px-4 py-2">
                  <Input value={row.quantity} onChange={(e) => update(row.id, "quantity", e.target.value)}
                    type="number" className="h-8 w-24 font-data" disabled={row.locked} />
                </td>

                {/* 평균단가 */}
                <td className="px-4 py-2">
                  <Input value={row.avg_price} onChange={(e) => update(row.id, "avg_price", e.target.value)}
                    type="number" className="h-8 w-28 font-data" disabled={row.locked} />
                </td>

                {/* 상태 */}
                <td className="px-4 py-2">
                  <span className="font-data text-xs text-muted-foreground" title={row.locked ? "증권사 동기화 데이터는 직접 수정할 수 없습니다." : undefined}>
                    {row.sourceSummary}
                  </span>
                </td>

                {/* 포트폴리오 포함 여부 */}
                <td className="px-4 py-2">
                  <button
                    type="button"
                    onClick={() => togglePortfolioVisibility(row.id)}
                    disabled={row.hasManual}
                    className={`border px-2 py-1 font-data text-[10px] ${
                      row.excludedFromPortfolio
                        ? "border-border text-muted-foreground hover:text-foreground"
                        : "border-primary text-primary"
                    } disabled:cursor-not-allowed disabled:border-border disabled:text-muted-foreground`}
                    title={row.excludedFromPortfolio ? "포트폴리오에서 숨김" : "포트폴리오에 포함"}
                  >
                    {row.excludedFromPortfolio ? "숨김" : "포함"}
                  </button>
                </td>

                {/* 상태 */}
                <td className="px-4 py-2">
                  <span className={`text-xs font-medium ${row.saved ? "text-muted-foreground" : "text-primary"}`}>
                    {row.saved ? "저장됨" : "미저장"}
                  </span>
                </td>

                {/* 액션 */}
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={row.locked || !row.ticker || lookingUp.has(row.id)}
                      onClick={() => handleLookup(row.id, row.ticker, row.market || undefined)}
                      className="h-8 w-8 p-0 font-data text-xs text-muted-foreground hover:text-foreground"
                      title="티커 정보 자동 조회"
                    >
                      {lookingUp.has(row.id) ? "…" : "🔍"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => remove(row)} disabled={row.locked}
                      className="h-8 text-xs text-error hover:text-error hover:bg-[rgba(221,60,68,0.08)]">삭제</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={addRow} className="w-full sm:w-auto">
          + 행 추가
        </Button>
        <Button onClick={save} disabled={saving} className="w-full sm:w-auto">
          {saving ? "저장 중…" : "저장"}
        </Button>
        {status && (
          <span className={`font-data text-xs ${status.startsWith("오류") ? "text-error" : "text-gain"}`}>
            {status}
          </span>
        )}
      </div>
    </div>
  );
}
