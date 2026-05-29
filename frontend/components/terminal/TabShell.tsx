"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { MarketsPanel } from "./panels/MarketsPanel";
// import { PortfolioPanel } from "./panels/PortfolioPanel";  // Task 8에서 추가
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
      {tab === "portfolio" && <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-muted)]">Portfolio Panel — Task 8에서 구현</div>}
      {tab === "research"  && <ResearchPanel />}
      {tab === "tools"     && <ToolsPanel />}
      {tab === "ai"        && <AiPanel />}
    </div>
  );
}

export function TabShell() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-secondary)]">
        로딩 중…
      </div>
    }>
      <TabShellInner />
    </Suspense>
  );
}
