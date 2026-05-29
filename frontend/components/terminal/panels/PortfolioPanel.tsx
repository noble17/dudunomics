"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { WatchlistWidget } from "@/components/terminal/widgets/Watchlist";
import { PortfolioWidget } from "@/components/terminal/widgets/Portfolio";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

function BreakdownPanel() {
  const { data: snapshot } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  if (!snapshot?.rows.length) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-muted)]">
        데이터 없음
      </div>
    );
  }

  const total = snapshot.total_equity_krw || 1;

  // 통화별 비중 집계
  const currencyMap: Record<string, number> = {};
  for (const row of snapshot.rows) {
    currencyMap[row.currency] = (currencyMap[row.currency] ?? 0) + row.market_value_krw;
  }
  const currencies = Object.entries(currencyMap).sort((a, b) => b[1] - a[1]);

  // 섹터별 비중 집계
  const sectorMap: Record<string, number> = {};
  for (const row of snapshot.rows) {
    const key = row.sector ?? "기타";
    sectorMap[key] = (sectorMap[key] ?? 0) + row.market_value_krw;
  }
  const sectors = Object.entries(sectorMap).sort((a, b) => b[1] - a[1]).slice(0, 6);

  function Bar({ pct, color }: { pct: number; color: string }) {
    return (
      <div className="h-1.5 rounded-full bg-[var(--color-bg-tertiary)] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-3 flex flex-col gap-4">
      <div>
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">통화 비중</p>
        {currencies.map(([currency, val]) => {
          const pct = (val / total) * 100;
          return (
            <div key={currency} className="mb-1.5">
              <div className="flex justify-between text-[10px] font-mono mb-0.5">
                <span className="text-[var(--color-text-secondary)]">{currency}</span>
                <span className="text-[var(--color-text-primary)]">{pct.toFixed(1)}%</span>
              </div>
              <Bar pct={pct} color="var(--color-primary)" />
            </div>
          );
        })}
      </div>
      <div>
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">섹터 비중</p>
        {sectors.map(([sector, val]) => {
          const pct = (val / total) * 100;
          return (
            <div key={sector} className="mb-1.5">
              <div className="flex justify-between text-[10px] font-mono mb-0.5">
                <span className="text-[var(--color-text-secondary)]">{sector}</span>
                <span className="text-[var(--color-text-primary)]">{pct.toFixed(1)}%</span>
              </div>
              <Bar pct={pct} color="var(--color-primary-dim)" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PortfolioPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        PORTFOLIO
      </div>
      <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
        <Panel defaultSize={25} minSize={15} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            WATCHLIST
          </div>
          <div className="flex-1 overflow-auto p-2">
            <WatchlistWidget />
          </div>
        </Panel>

        <ResizeHandle />

        <Panel defaultSize={50} minSize={30} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            HOLDINGS
          </div>
          <div className="flex-1 overflow-auto">
            <PortfolioWidget />
          </div>
        </Panel>

        <ResizeHandle />

        <Panel defaultSize={25} minSize={15} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            BREAKDOWN
          </div>
          <BreakdownPanel />
        </Panel>
      </PanelGroup>
    </div>
  );
}
