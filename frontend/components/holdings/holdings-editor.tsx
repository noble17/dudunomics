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
  saved: boolean;
  lookupError: boolean;
}

function toRow(h: HoldingOut): Row {
  return {
    id: h.ticker,
    ticker: h.ticker,
    name: h.name,
    sector: h.sector ?? "",
    market: (h as HoldingOut & { market?: string }).market ?? "",
    currency: h.currency as "KRW" | "USD",
    quantity: String(h.quantity),
    avg_price: String(h.avg_price),
    saved: true,
    lookupError: false,
  };
}

interface Props {
  initialHoldings: HoldingOut[];
  initialCashKrw: number;
  initialCashUsd: number;
}

export function HoldingsEditor({ initialHoldings, initialCashKrw, initialCashUsd }: Props) {
  const [rows, setRows] = useState<Row[]>(initialHoldings.map(toRow));
  const [savedTickers, setSavedTickers] = useState<Set<string>>(
    () => new Set(initialHoldings.map((h) => h.ticker))
  );
  const [cashKrw, setCashKrw] = useState(String(initialCashKrw));
  const [cashUsd, setCashUsd] = useState(String(initialCashUsd));
  const [saving, setSaving] = useState(false);
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
        id: crypto.randomUUID(),
        ticker: "", name: "", sector: "", market: "",
        currency: "KRW", quantity: "0", avg_price: "0",
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

  const save = async () => {
    setSaving(true);
    setStatus("");
    try {
      const existing = [...savedTickers];
      const current = rows.map((r) => r.ticker).filter(Boolean);
      for (const t of existing) {
        if (!current.includes(t)) await holdingsApi.delete(t);
      }
      for (const row of rows) {
        if (!row.ticker) continue;
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
      setSavedTickers(new Set(rows.map((r) => r.ticker).filter(Boolean)));
      setStatus("저장 완료");
    } catch (e: unknown) {
      setStatus(`오류: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
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
        </div>
      </div>

      {/* 종목 테이블 */}
      <div className="border border-border">
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-[var(--card)]">
            <tr>
              {["티커", "종목명", "섹터", "시장", "통화", "수량", "평균단가", "상태", ""].map((h) => (
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
                    />
                  )}
                </td>

                {/* 통화 */}
                <td className="px-4 py-2">
                  <Select value={row.currency} onValueChange={(v) => { if (v) update(row.id, "currency", v); }}>
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
                    type="number" className="h-8 w-24 font-data" />
                </td>

                {/* 평균단가 */}
                <td className="px-4 py-2">
                  <Input value={row.avg_price} onChange={(e) => update(row.id, "avg_price", e.target.value)}
                    type="number" className="h-8 w-28 font-data" />
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
                      disabled={!row.ticker || lookingUp.has(row.id)}
                      onClick={() => handleLookup(row.id, row.ticker, row.market || undefined)}
                      className="h-8 w-8 p-0 font-data text-xs text-muted-foreground hover:text-foreground"
                      title="티커 정보 자동 조회"
                    >
                      {lookingUp.has(row.id) ? "…" : "🔍"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => remove(row)}
                      className="h-8 text-xs text-error hover:text-error hover:bg-[rgba(221,60,68,0.08)]">삭제</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={addRow}>
          + 행 추가
        </Button>
        <Button onClick={save} disabled={saving}>
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
