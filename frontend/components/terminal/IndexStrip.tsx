"use client";

import { useQuotes } from "@/hooks/useQuotes";
import type { QuoteItem } from "@/lib/types";

function fmt(value: number, decimals: number): string {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function QuoteCell({ label, item, decimals }: {
  label: string;
  item: QuoteItem | null | undefined;
  decimals: number;
}) {
  const up = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;
  const changeColor = up
    ? "text-[var(--color-gain)]"
    : down
    ? "text-[var(--color-loss)]"
    : "text-[var(--color-text-secondary)]";
  const arrow = up ? "▲" : down ? "▼" : "";

  return (
    <div className="flex items-center gap-1.5 text-xs shrink-0">
      <span className="text-[var(--color-text-secondary)] font-medium">{label}</span>
      <span className="text-[var(--color-text-primary)] font-mono">
        {item ? fmt(item.price, decimals) : "—"}
      </span>
      {item && (
        <span className={`font-mono text-[10px] ${changeColor}`}>
          {arrow}{item.change_abs >= 0 ? "+" : ""}{fmt(item.change_abs, decimals)}{" "}
          ({item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%)
        </span>
      )}
    </div>
  );
}

export function IndexStrip() {
  const quotes = useQuotes();

  return (
    <div className="flex items-center gap-6 px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0 overflow-x-auto">
      <QuoteCell label="SPY"     item={quotes?.SPY}    decimals={2} />
      <QuoteCell label="QQQ"     item={quotes?.QQQ}    decimals={2} />
      <QuoteCell label="USD/KRW" item={quotes?.USDKRW} decimals={1} />
      <QuoteCell label="BTC"     item={quotes?.BTC}    decimals={0} />
    </div>
  );
}
