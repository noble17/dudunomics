export function AiPanel() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4">
      <div className="text-center">
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">
          AI ASSISTANT
        </p>
        <p className="text-xs font-mono text-[var(--color-text-muted)]">
          Gemini API — M6에서 연결 예정
        </p>
      </div>
      <button
        disabled
        className="text-xs font-mono text-[var(--color-text-muted)] border border-[var(--color-placeholder)] rounded px-4 py-2 cursor-not-allowed opacity-50"
      >
        API 키 설정
      </button>
    </div>
  );
}
