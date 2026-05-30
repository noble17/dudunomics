"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { MarketsPanel } from "./panels/MarketsPanel";
import { PortfolioPanel } from "./panels/PortfolioPanel";
import { ResearchPanel } from "./panels/ResearchPanel";
import { ToolsPanel } from "./panels/ToolsPanel";
import { AiPanel } from "./panels/AiPanel";

type TabKey = "markets" | "portfolio" | "research" | "tools" | "ai";
const VALID_TABS: TabKey[] = ["markets", "portfolio", "research", "tools", "ai"];

function TabShellInner() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("tab") ?? "markets";
  const tab: TabKey = VALID_TABS.includes(raw as TabKey) ? (raw as TabKey) : "markets";

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {tab === "markets"   && <MarketsPanel />}
      {tab === "portfolio" && <PortfolioPanel />}
      {tab === "research"  && <ResearchPanel />}
      {tab === "tools"     && <ToolsPanel />}
      {tab === "ai"        && <AiPanel />}
    </div>
  );
}

export function TabShell() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center text-xs font-data text-[var(--color-text-secondary)]">
        로딩 중…
      </div>
    }>
      <TabShellInner />
    </Suspense>
  );
}
