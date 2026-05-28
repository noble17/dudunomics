"use client";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";

export function ScreenerWidget() {
  const { data: scores, isLoading } = useSWR("/api/screener/scores?universe=sp500", () => screenerApi.scores(), { refreshInterval: 300_000 });

  if (isLoading) return <div className="text-xs text-muted-foreground">로딩 중…</div>;
  if (!scores?.length) return <div className="text-xs text-muted-foreground">데이터 없음</div>;

  const top = [...scores].sort((a, b) => {
    const sa = (a.pct_momentum ?? 0) + (a.pct_quality ?? 0);
    const sb = (b.pct_momentum ?? 0) + (b.pct_quality ?? 0);
    return sb - sa;
  }).slice(0, 20);

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[var(--color-text-secondary)] border-b border-[var(--color-border)]">
          <th className="text-left py-1 pr-2">티커</th>
          <th className="text-right py-1 pr-2">모멘텀</th>
          <th className="text-right py-1">밸류</th>
        </tr>
      </thead>
      <tbody>
        {top.map(s => (
          <tr key={s.ticker} className="border-b border-[var(--color-border)]/50">
            <td className="py-1 pr-2 font-mono font-medium text-[var(--color-text-primary)]">{s.ticker}</td>
            <td className="py-1 pr-2 text-right">{s.pct_momentum != null ? `${(s.pct_momentum * 100).toFixed(0)}%` : "—"}</td>
            <td className="py-1 text-right">{s.pct_valuation != null ? `${(s.pct_valuation * 100).toFixed(0)}%` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
