"use client";
import useSWR from "swr";
import { holdingsApi } from "@/lib/api";
import { useCommandStore } from "@/lib/stores/command";

export function WatchlistWidget() {
  const { data: holdings, isLoading } = useSWR("/api/holdings", holdingsApi.list, { refreshInterval: 30_000 });
  const setFocused = useCommandStore(s => s.setFocusedTicker);

  if (isLoading) return <div className="text-xs text-muted-foreground">로딩 중…</div>;
  if (!holdings?.length) return <div className="text-xs text-muted-foreground">보유종목 없음</div>;

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[var(--color-text-secondary)] border-b border-[var(--color-border)]">
          <th className="text-left py-1 pr-2">티커</th>
          <th className="text-right py-1 pr-2">수량</th>
          <th className="text-right py-1">수익률</th>
        </tr>
      </thead>
      <tbody>
        {holdings.map(h => (
          <tr
            key={h.ticker}
            className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-bg-primary)] cursor-pointer"
            onClick={() => setFocused(h.ticker)}
          >
            <td className="py-1 pr-2 font-mono font-medium text-[var(--color-text-primary)]">{h.ticker}</td>
            <td className="py-1 pr-2 text-right text-[var(--color-text-secondary)]">{h.quantity}</td>
            <td className="py-1 text-right text-[var(--color-text-secondary)]">—</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
