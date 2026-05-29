"use client";
import { useState } from "react";
import useSWR from "swr";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { quotesApi, portfolioApi, holdingsApi, aiApi } from "@/lib/api";
import { useCommandStore } from "@/lib/stores/command";
import { CandleChart } from "@/components/terminal/widgets/CandleChart";
import { WatchlistWidget } from "@/components/terminal/widgets/Watchlist";
import { NewsPanel } from "@/components/terminal/widgets/NewsPanel";
import { AIStatusBar } from "@/components/terminal/widgets/AIStatusBar";
import { AIOverlay } from "@/components/terminal/widgets/AIOverlay";
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

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

export function MarketsPanel() {
  const { data: quotes } = useSWR("/api/quotes", quotesApi.get, { refreshInterval: 10_000 });
  const { data: snapshot } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });
  const focusedTicker = useCommandStore((s) => s.focusedTicker);
  const { data: holdings } = useSWR("/api/holdings", holdingsApi.list, { dedupingInterval: 30_000 });
  const chartTicker = focusedTicker ?? holdings?.[0]?.ticker ?? "SPY";

  const [aiOpen, setAiOpen] = useState(false);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  async function handleAiOpen() {
    setAiOpen(true);
    if (!aiSummary) {
      setAiLoading(true);
      try {
        const { summary } = await aiApi.summary(chartTicker);
        setAiSummary(summary);
      } catch {
        // 요약 실패해도 채팅은 열림
      } finally {
        setAiLoading(false);
      }
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Row 1: Market Overview 타일 */}
      <div className="h-20 shrink-0 flex items-stretch border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="flex items-stretch flex-1 overflow-x-auto">
          {TILES.map(tile => (
            <MarketTile key={tile.label} config={tile} quotes={quotes ?? null} />
          ))}
        </div>
      </div>

      {/* Row 2: 3분할 드래그 패널 */}
      <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
        {/* 좌: Watchlist */}
        <Panel defaultSize={20} minSize={12} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            WATCHLIST
          </div>
          <div className="flex-1 overflow-auto p-2">
            <WatchlistWidget />
          </div>
        </Panel>

        <ResizeHandle />

        {/* 중: Chart */}
        <Panel defaultSize={50} minSize={20} className="flex flex-col overflow-hidden border-x border-[var(--color-border)]">
          <CandleChart ticker={chartTicker} />
        </Panel>

        <ResizeHandle />

        {/* 우: Top News */}
        <Panel defaultSize={30} minSize={12} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            TOP NEWS
          </div>
          <div className="flex-1 overflow-auto">
            <NewsPanel ticker={chartTicker} />
          </div>
        </Panel>
      </PanelGroup>

      {/* Row 3: 포트폴리오 요약 + AI */}
      <div className="h-[72px] shrink-0 flex border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        {/* 좌: MY PORTFOLIO */}
        <div className="flex-1 flex flex-col justify-center px-4 border-r border-[var(--color-border)]">
          <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-1">
            MY PORTFOLIO
          </p>
          {snapshot ? (
            <div className="flex items-baseline gap-4">
              <span className="text-[13px] font-mono text-[var(--color-text-primary)]">
                ₩{snapshot.total_with_cash_krw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
              </span>
              <span className="text-[10px] font-mono text-[var(--color-text-secondary)]">
                오늘 손익 <span className="text-[var(--color-text-muted)]">—</span>
              </span>
            </div>
          ) : (
            <span className="text-[11px] font-mono text-[var(--color-text-muted)]">로딩 중…</span>
          )}
        </div>
        {/* 우: AI ASSISTANT */}
        <div className="flex-1 flex">
          <AIStatusBar
            summary={aiSummary}
            loading={aiLoading}
            onOpen={handleAiOpen}
          />
        </div>
      </div>

      {/* AI 채팅 오버레이 */}
      {aiOpen && (
        <AIOverlay
          ticker={chartTicker}
          initialSummary={aiSummary}
          onClose={() => setAiOpen(false)}
        />
      )}
    </div>
  );
}
