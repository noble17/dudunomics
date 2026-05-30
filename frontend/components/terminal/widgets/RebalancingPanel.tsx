"use client";
import { useState } from "react";
import useSWR from "swr";
import { rebalancingApi } from "@/lib/api";

export function RebalancingPanel() {
  const { data: rows, mutate, isLoading } = useSWR(
    "/api/portfolio/rebalancing",
    rebalancingApi.get,
    { refreshInterval: 60_000 }
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");

  async function saveTarget(ticker: string) {
    const val = parseFloat(editVal);
    await rebalancingApi.setTargetWeight(ticker, isNaN(val) ? null : val);
    setEditing(null);
    mutate();
  }

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[#ff9500] border-b border-[var(--color-border)] shrink-0">
        REBALANCING
      </div>
      <div className="flex-1 overflow-auto px-3 py-1">
        {!rows?.length && (
          <div className="text-[10px] font-mono text-[var(--color-text-muted)] mt-2">데이터 없음</div>
        )}
        <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
          <span>Ticker</span>
          <span className="text-right">현재→목표</span>
          <span className="text-right">액션</span>
        </div>
        {rows?.map((row) => (
          <div key={row.ticker} className="grid grid-cols-3 py-1 border-b border-[var(--color-border)] items-center">
            <span
              className="text-[10px] font-mono text-[var(--color-text-primary)] cursor-pointer hover:text-[var(--color-primary)]"
              onClick={() => { setEditing(row.ticker); setEditVal(String(row.target_weight ?? "")); }}
            >
              {row.ticker}
            </span>
            <div className="text-right text-[10px] font-mono text-[var(--color-text-secondary)]">
              {editing === row.ticker ? (
                <input
                  type="number"
                  value={editVal}
                  onChange={(e) => setEditVal(e.target.value)}
                  onBlur={() => saveTarget(row.ticker)}
                  onKeyDown={(e) => e.key === "Enter" && saveTarget(row.ticker)}
                  className="w-16 bg-[var(--color-bg-tertiary)] border border-[var(--color-primary)] text-[var(--color-text-primary)] px-1 text-right font-mono text-[10px]"
                  autoFocus
                />
              ) : (
                <span>
                  {row.current_weight.toFixed(1)}%
                  {row.target_weight != null ? `→${row.target_weight.toFixed(1)}%` : ""}
                </span>
              )}
            </div>
            <div className="text-right text-[10px] font-mono">
              {row.action === "BUY" && (
                <span className="text-green-400">▲ ₩{(row.amount_krw / 10_000).toFixed(0)}만</span>
              )}
              {row.action === "SELL" && (
                <span className="text-red-400">▼ ₩{(row.amount_krw / 10_000).toFixed(0)}만</span>
              )}
              {row.action === "HOLD" && <span className="text-[var(--color-text-muted)]">HOLD</span>}
              {row.action === "NO_TARGET" && (
                <span
                  className="text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-primary)]"
                  onClick={() => { setEditing(row.ticker); setEditVal(""); }}
                >
                  설정
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
