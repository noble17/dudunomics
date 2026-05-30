"use client";
import { useEffect, useRef, useState } from "react";
import { aiApi } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface Props {
  ticker: string;
  initialSummary: string | null;
  onClose: () => void;
}

export function AIOverlay({ ticker, initialSummary, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    initialSummary
      ? [{ role: "assistant", content: initialSummary }]
      : [],
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || streaming) return;
    const userMsg: ChatMessage = { role: "user", content: input.trim() };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setStreaming(true);

    const assistantMsg: ChatMessage = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMsg]);

    await aiApi.streamChat(updatedMessages, ticker, (chunk) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last.role !== "assistant") return prev;
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + chunk },
        ];
      });
    });
    setStreaming(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      {/* 배경 dimmer */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* 슬라이드업 패널 */}
      <div className="relative flex flex-col bg-[#111] border-t border-[var(--color-border)] h-[60vh] z-10">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)] shrink-0">
          <span className="text-[12px] font-data uppercase tracking-widest text-[var(--color-primary)]">
            AI ASSISTANT — {ticker}
          </span>
          <button
            onClick={onClose}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] text-sm leading-none"
          >
            ✕
          </button>
        </div>

        {/* 메시지 목록 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <p className="text-[13px] font-data text-[var(--color-text-muted)] text-center mt-8">
              {ticker}에 대해 질문해보세요
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={[
                  "max-w-[80%] px-3 py-2 rounded text-[13px] font-data leading-relaxed whitespace-pre-wrap",
                  msg.role === "user"
                    ? "bg-[var(--color-primary)] text-black"
                    : "bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)]",
                ].join(" ")}
              >
                {msg.content || (streaming && i === messages.length - 1 ? "▋" : "")}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* 입력창 */}
        <div className="shrink-0 flex items-center gap-2 px-4 py-3 border-t border-[var(--color-border)]">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder={`${ticker} 에 대해 질문…`}
            disabled={streaming}
            className="flex-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-3 py-1.5 text-[13px] font-data text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="px-3 py-1.5 bg-[var(--color-primary)] text-black text-[12px] font-data rounded hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
}
