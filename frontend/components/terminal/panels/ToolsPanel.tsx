import { BacktestWidget } from "@/components/terminal/widgets/Backtest";

export function ToolsPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        TOOLS — BACKTEST
      </div>
      <div className="flex-1 overflow-auto p-4">
        <BacktestWidget />
      </div>
    </div>
  );
}
