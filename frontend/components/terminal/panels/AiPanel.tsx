"use client";
import { useEffect, useRef, useState } from "react";
import { aiApi } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export function AiPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || streaming) return;
    const userMsg: ChatMessage = { role: "user", content: input.trim() };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput("");
    setStreaming(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    await aiApi.streamChat(updated, null, (chunk) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
      });
    });
    setStreaming(false);
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        AI — ASSISTANT
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-[13px] font-data text-[var(--color-text-muted)] text-center mt-16">
            주식·시장에 대해 질문해보세요
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
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

      <div className="shrink-0 flex items-center gap-2 px-4 py-3 border-t border-[var(--color-border)]">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="주식·시장에 대해 질문…"
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
  );
}
