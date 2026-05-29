"use client";
import useSWR from "swr";
import { quotesApi } from "@/lib/api";
import type { QuotesOut } from "@/lib/types";

type TileConfig = {
  label: string;
  quoteKey: keyof QuotesOut | null;
  decimals: number;
};

const TILES: TileConfig[] = [
  { label: "SPY",     quoteKey: "SPY",  decimals: 2 },
  { label: "QQQ",     quoteKey: "QQQ",  decimals: 2 },
  { label: "DJI",     quoteKey: null,   decimals: 0 },
  { label: "VIX",     quoteKey: null,   decimals: 2 },
  { label: "US10Y",   quoteKey: null,   decimals: 2 },
  { label: "WTI",     quoteKey: null,   decimals: 2 },
  { label: "GOLD",    quoteKey: null,   decimals: 0 },
  { label: "BTC/USD", quoteKey: "BTC",  decimals: 0 },
];

function fmt(value: number, decimals: number): string {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function MarketTile({ config, quotes }: { config: TileConfig; quotes: QuotesOut | null }) {
  const item = config.quoteKey ? quotes?.[config.quoteKey] : null;
  const up   = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;

  return (
    <div className="flex flex-col justify-center px-3 border-r border-[var(--color-border)] shrink-0 min-w-[88px]">
      <span className="text-[9px] font-mono uppercase tracking-wider text-[var(--color-text-secondary)]">
        {config.label}
      </span>
      {item ? (
        <>
          <span className="text-[11px] font-mono text-[var(--color-text-primary)] leading-tight">
            {fmt(item.price, config.decimals)}
          </span>
          <span
            className={[
              "text-[10px] font-mono leading-tight",
              up   ? "text-[var(--color-gain)]" :
              down ? "text-[var(--color-loss)]" :
                     "text-[var(--color-text-muted)]",
            ].join(" ")}
          >
            {up ? "▲" : down ? "▼" : ""}
            {item.change_pct >= 0 ? "+" : ""}
            {item.change_pct.toFixed(2)}%
          </span>
        </>
      ) : (
        <>
          <span className="text-[11px] font-mono text-[var(--color-text-muted)]">—</span>
          {config.quoteKey === null && (
            <span className="text-[9px] font-mono text-[var(--color-placeholder)]">API 필요</span>
          )}
        </>
      )}
    </div>
  );
}

export function MarketsPanel() {
  const { data: quotes } = useSWR("/api/quotes", quotesApi.get, { refreshInterval: 10_000 });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Row 1: Market Overview 타일 (height: 80px) */}
      <div className="h-20 shrink-0 flex items-stretch border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="flex items-stretch flex-1 overflow-x-auto">
          {TILES.map(tile => (
            <MarketTile key={tile.label} config={tile} quotes={quotes ?? null} />
          ))}
        </div>
      </div>

      {/* Row 2: 3분할 패널 — Task 6에서 구현 */}
      <div className="flex-1 overflow-hidden flex items-center justify-center text-xs font-mono text-[var(--color-text-muted)]">
        Row 2 — Task 6에서 구현
      </div>

      {/* Row 3: 포트폴리오 요약 — Task 7에서 구현 */}
      <div className="h-[72px] shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]" />
    </div>
  );
}
