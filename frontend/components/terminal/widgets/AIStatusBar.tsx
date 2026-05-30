"use client";

interface Props {
  summary: string | null;
  loading: boolean;
  onOpen: () => void;
}

export function AIStatusBar({ summary, loading, onOpen }: Props) {
  return (
    <div className="flex-1 flex flex-col justify-center px-4">
      <p className="text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)] mb-0.5">
        AI ASSISTANT
      </p>
      <button
        onClick={onOpen}
        className="flex items-center justify-between w-full text-left group"
      >
        <span className="text-[12px] font-data text-[var(--color-text-muted)] truncate flex-1 pr-2">
          {loading
            ? "분석 중…"
            : summary
            ? summary
            : "클릭하여 AI 분석 시작"}
        </span>
        <span className="text-[11px] font-data text-[var(--color-primary)] shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          ↑ 채팅
        </span>
      </button>
    </div>
  );
}
