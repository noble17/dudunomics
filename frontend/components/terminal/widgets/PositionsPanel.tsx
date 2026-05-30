"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";

interface Props {
  onTickerSelect?: (ticker: string) => void;
  selectedTicker?: string;
}

export function PositionsPanel({ onTickerSelect, selectedTicker }: Props) {
  const { data: snapshot, isLoading } = useSWR(
    "/api/portfolio/current",
    portfolioApi.current,
    { refreshInterval: 30_000 }
  );

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );
  if (!snapshot?.rows.length) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">보유 종목 없음</div>
  );

  const realizedPnl = (snapshot as any).realized_pnl_krw ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        POSITIONS
      </div>
      <div className="flex-1 overflow-auto">
        <div className="px-3 py-1">
          <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
            <span>Ticker</span>
            <span className="text-right">수익률</span>
            <span className="text-right">평가액</span>
          </div>
          {snapshot.rows.map((row) => (
            <div
              key={row.ticker}
              onClick={() => onTickerSelect?.(row.ticker)}
              className={`grid grid-cols-3 py-1 border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] text-[10px] font-mono ${
                selectedTicker === row.ticker ? "bg-[var(--color-bg-tertiary)]" : ""
              }`}
            >
              <span className="text-[var(--color-text-primary)]">{row.ticker}</span>
              <span className={`text-right ${row.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                {row.return_pct >= 0 ? "+" : ""}{row.return_pct.toFixed(1)}%
              </span>
              <span className="text-right text-[var(--color-text-secondary)]">
                ₩{(row.market_value_krw / 1_000_000).toFixed(1)}M
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="px-3 py-2 border-t border-[var(--color-border)] shrink-0 space-y-0.5">
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">총 평가</span>
          <span className="text-[var(--color-text-primary)]">
            ₩{(snapshot.total_equity_krw / 1_000_000).toFixed(1)}M
          </span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">실현 손익</span>
          <span className={realizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
            {realizedPnl >= 0 ? "+" : ""}₩{(realizedPnl / 10_000).toFixed(0)}만
          </span>
        </div>
      </div>
    </div>
  );
}
