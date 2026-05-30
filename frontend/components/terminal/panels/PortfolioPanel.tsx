"use client";
import { useState } from "react";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { PositionsPanel } from "@/components/terminal/widgets/PositionsPanel";
import { RebalancingPanel } from "@/components/terminal/widgets/RebalancingPanel";
import { PerformancePanel } from "@/components/terminal/widgets/PerformancePanel";
import { TradeLogPanel } from "@/components/terminal/widgets/TradeLogPanel";

function ResizeHandle({ vertical = false }: { vertical?: boolean }) {
  return vertical ? (
    <PanelResizeHandle className="h-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors my-0.5" />
  ) : (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

export function PortfolioPanel() {
  const [selectedTicker, setSelectedTicker] = useState<string | undefined>();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        PORTFOLIO
      </div>
      <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">

        {/* 왼쪽 사이드바: Positions + Rebalancing */}
        <Panel defaultSize={28} minSize={20} className="flex flex-col overflow-hidden">
          <PanelGroup orientation="vertical" className="flex-1 overflow-hidden">
            <Panel defaultSize={55} minSize={30} className="flex flex-col overflow-hidden">
              <PositionsPanel
                onTickerSelect={setSelectedTicker}
                selectedTicker={selectedTicker}
              />
            </Panel>
            <ResizeHandle vertical />
            <Panel defaultSize={45} minSize={20} className="flex flex-col overflow-hidden">
              <RebalancingPanel />
            </Panel>
          </PanelGroup>
        </Panel>

        <ResizeHandle />

        {/* 오른쪽: Performance + Trade Log */}
        <Panel defaultSize={72} minSize={40} className="flex flex-col overflow-hidden">
          <PanelGroup orientation="vertical" className="flex-1 overflow-hidden">
            <Panel defaultSize={55} minSize={30} className="flex flex-col overflow-hidden">
              <PerformancePanel />
            </Panel>
            <ResizeHandle vertical />
            <Panel defaultSize={45} minSize={25} className="flex flex-col overflow-hidden">
              <TradeLogPanel filterTicker={selectedTicker} />
            </Panel>
          </PanelGroup>
        </Panel>

      </PanelGroup>
    </div>
  );
}
