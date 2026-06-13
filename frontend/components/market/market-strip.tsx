"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { useQuotes } from "@/hooks/useQuotes";
import type { QuoteItem } from "@/lib/types";

function format(value: number, decimals: number) {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function MarketCell({ label, item, decimals }: { label: string; item?: QuoteItem | null; decimals: number }) {
  const up = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;
  const color = up ? "text-gain" : down ? "text-loss" : "text-muted-foreground";

  return (
    <div className="flex shrink-0 items-center gap-2 border-r border-border px-4 py-2 last:border-r-0">
      <span className="font-data text-xs text-muted-foreground">{label}</span>
      <span className="font-data text-sm text-foreground">{item ? format(item.price, decimals) : "-"}</span>
      {item && (
        <span className={`font-data text-xs ${color}`}>
          {up ? "▲" : down ? "▼" : ""}
          {item.change_pct >= 0 ? "+" : ""}
          {item.change_pct.toFixed(2)}%
        </span>
      )}
    </div>
  );
}

const EST_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function MarketStrip() {
  const quotes = useQuotes();
  const [clock, setClock] = useState(() => EST_FORMATTER.format(new Date()));

  useEffect(() => {
    const id = setInterval(() => setClock(EST_FORMATTER.format(new Date())), 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="overflow-x-auto border border-border bg-card">
      <div className="flex min-w-max items-stretch lg:min-w-full">
        <div className="flex shrink-0 items-center gap-2 border-r border-border px-4 py-2">
          <span className="font-data text-[10px] tracking-[0.24em] text-primary">MARKET</span>
          <span className="font-data text-xs text-muted-foreground">NY {clock}</span>
          {quotes?.updated_at && (
            <span className="font-data text-[10px] text-muted-foreground">
              갱신 {new Date(quotes.updated_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
        <MarketCell label="SPY" item={quotes?.SPY} decimals={2} />
        <MarketCell label="QQQ" item={quotes?.QQQ} decimals={2} />
        <MarketCell label="USD/KRW" item={quotes?.USDKRW} decimals={1} />
        <MarketCell label="BTC" item={quotes?.BTC} decimals={0} />
        <MarketCell label="VIX" item={quotes?.VIX} decimals={2} />
        <MarketCell label="US10Y" item={quotes?.US10Y} decimals={2} />
        <MarketCell label="GOLD" item={quotes?.GOLD} decimals={0} />
        <Link
          href="/portfolio/holdings"
          className="ml-auto flex shrink-0 items-center gap-2 border-l border-border px-4 py-2 font-data text-xs text-muted-foreground transition-colors hover:text-primary"
          title="보유종목 관리"
        >
          <Settings className="h-4 w-4" />
          <span>보유관리</span>
        </Link>
      </div>
    </section>
  );
}
