import { ScreenerWidget } from "@/components/terminal/widgets/Screener";

export function ResearchPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        RESEARCH — QUANT SCREENER
      </div>
      <div className="flex-1 overflow-auto p-4">
        <ScreenerWidget />
      </div>
    </div>
  );
}
