"use client";

const INDICES = [
  { label: "SPY", value: "—", change: null },
  { label: "QQQ", value: "—", change: null },
  { label: "USD/KRW", value: "—", change: null },
  { label: "BTC", value: "—", change: null },
];

export function IndexStrip() {
  return (
    <div className="flex items-center gap-6 px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0 overflow-x-auto">
      {INDICES.map(idx => (
        <div key={idx.label} className="flex items-center gap-1.5 text-xs shrink-0">
          <span className="text-[var(--color-text-secondary)] font-medium">{idx.label}</span>
          <span className="text-[var(--color-text-primary)] font-mono">
            {idx.value}
          </span>
          <span className="text-[var(--color-text-secondary)] text-[10px]">M3에서 실시간 연결</span>
        </div>
      ))}
    </div>
  );
}
