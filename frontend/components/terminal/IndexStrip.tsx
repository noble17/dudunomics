"use client";
import { useEffect, useState } from "react";
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
    <div className="flex items-center gap-1.5 text-[13px] shrink-0">
      <span className="text-[var(--color-text-secondary)] font-data">{label}</span>
      <span className="text-[var(--color-text-primary)] font-data">
        {item ? fmt(item.price, decimals) : "—"}
      </span>
      {item && (
        <span className={`font-data text-[12px] ${changeColor}`}>
          {arrow}{item.change_abs >= 0 ? "+" : ""}{fmt(item.change_abs, decimals)}{" "}
          ({item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%)
        </span>
      )}
    </div>
  );
}

const EST_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function IndexStrip() {
  const quotes = useQuotes();
  const [clock, setClock] = useState(() => EST_FORMATTER.format(new Date()));

  useEffect(() => {
    const id = setInterval(() => setClock(EST_FORMATTER.format(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      {/* 좌: INDICES 레이블 */}
      <span className="text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)] mr-4 shrink-0">
        INDICES ▾
      </span>

      {/* 시세 셀 */}
      <div className="flex items-center gap-6 flex-1 overflow-x-auto">
        <QuoteCell label="SPY"     item={quotes?.SPY}    decimals={2} />
        <QuoteCell label="QQQ"     item={quotes?.QQQ}    decimals={2} />
        <QuoteCell label="USD/KRW" item={quotes?.USDKRW} decimals={1} />
        <QuoteCell label="BTC"     item={quotes?.BTC}    decimals={0} />
      </div>

      {/* 우: Connected + EST 시각 */}
      <div className="flex items-center gap-2 shrink-0 ml-4">
        <span className="text-[11px] font-data text-[var(--color-connected)]">● Connected</span>
        <span className="text-[12px] font-data text-[var(--color-text-muted)]">NY {clock} EST</span>
      </div>
    </div>
  );
}
