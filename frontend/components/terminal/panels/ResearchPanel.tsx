import { ScreenerWidget } from "@/components/terminal/widgets/Screener";

export function ResearchPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 border-b border-[var(--color-border)] shrink-0">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">리서치</span>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <ScreenerWidget />
      </div>
    </div>
  );
}
