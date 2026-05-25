"use client";

import { useState } from "react";
import { holdingsApi } from "@/lib/api";
import type { HoldingOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

interface Row {
  id: string;
  ticker: string;
  name: string;
  currency: "KRW" | "USD";
  quantity: string;
  avg_price: string;
  saved: boolean;
}

function toRow(h: HoldingOut): Row {
  return {
    id: h.ticker,
    ticker: h.ticker,
    name: h.name,
    currency: h.currency as "KRW" | "USD",
    quantity: String(h.quantity),
    avg_price: String(h.avg_price),
    saved: true,
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

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      { id: crypto.randomUUID(), ticker: "", name: "", currency: "KRW", quantity: "0", avg_price: "0", saved: false },
    ]);

  const update = (id: string, field: keyof Pick<Row, "ticker" | "name" | "currency" | "quantity" | "avg_price">, value: string) =>
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value, saved: false } : r)));

  const remove = async (row: Row) => {
    if (row.ticker && row.saved) await holdingsApi.delete(row.ticker);
    setRows((prev) => prev.filter((r) => r.id !== row.id));
  };

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
      setStatus("저장 완료 ✓");
    } catch (e: unknown) {
      setStatus(`오류: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 현금 입력 */}
      <div className="rounded-lg border bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-muted-foreground">현금 잔고</h3>
        <div className="flex flex-wrap gap-4">
          <div className="space-y-1">
            <Label>현금 (KRW)</Label>
            <Input value={cashKrw} onChange={(e) => setCashKrw(e.target.value)}
              type="number" className="w-40" />
          </div>
          <div className="space-y-1">
            <Label>현금 (USD)</Label>
            <Input value={cashUsd} onChange={(e) => setCashUsd(e.target.value)}
              type="number" className="w-40" />
          </div>
        </div>
      </div>

      {/* 종목 테이블 */}
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b bg-slate-50 text-xs uppercase text-muted-foreground">
            <tr>
              {["티커", "종목명", "통화", "수량", "평균단가", "상태", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b last:border-0">
                <td className="px-4 py-2">
                  <Input value={row.ticker} onChange={(e) => update(row.id, "ticker", e.target.value)}
                    className="h-8 w-32 font-mono" placeholder="005930.KS" />
                </td>
                <td className="px-4 py-2">
                  <Input value={row.name} onChange={(e) => update(row.id, "name", e.target.value)}
                    className="h-8 w-36" placeholder="종목명" />
                </td>
                <td className="px-4 py-2">
                  <Select value={row.currency} onValueChange={(v) => { if (v) update(row.id, "currency", v); }}>
                    <SelectTrigger className="h-8 w-20"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="KRW">KRW</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                    </SelectContent>
                  </Select>
                </td>
                <td className="px-4 py-2">
                  <Input value={row.quantity} onChange={(e) => update(row.id, "quantity", e.target.value)}
                    type="number" className="h-8 w-24" />
                </td>
                <td className="px-4 py-2">
                  <Input value={row.avg_price} onChange={(e) => update(row.id, "avg_price", e.target.value)}
                    type="number" className="h-8 w-28" />
                </td>
                <td className="px-4 py-2">
                  <Badge variant={row.saved ? "outline" : "secondary"}>
                    {row.saved ? "저장됨" : "미저장"}
                  </Badge>
                </td>
                <td className="px-4 py-2">
                  <Button variant="ghost" size="sm" onClick={() => remove(row)}
                    className="h-8 text-destructive hover:text-destructive">삭제</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={addRow}>+ 행 추가</Button>
        <Button onClick={save} disabled={saving}>
          {saving ? "저장 중…" : "저장"}
        </Button>
        {status && <span className={`text-sm ${status.startsWith("오류") ? "text-destructive" : "text-emerald-600"}`}>{status}</span>}
      </div>
    </div>
  );
}
