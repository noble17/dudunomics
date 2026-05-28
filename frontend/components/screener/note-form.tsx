// frontend/components/screener/note-form.tsx
"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import type { TickerNote } from "@/lib/types";

export function NoteForm({ ticker }: { ticker: string }) {
  const { data: saved, mutate } = useSWR(
    `/api/screener/notes/${ticker}`,
    () => screenerApi.getNote(ticker)
  );

  const [opinion, setOpinion]         = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [memo, setMemo]               = useState("");
  const [tags, setTags]               = useState("");
  const [saving, setSaving]           = useState(false);

  useEffect(() => {
    if (saved) {
      setOpinion(saved.opinion ?? "");
      setTargetPrice(saved.target_price?.toString() ?? "");
      setMemo(saved.memo ?? "");
      setTags(saved.tags ?? "");
    }
  }, [saved]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await screenerApi.upsertNote(ticker, {
        opinion: opinion || null,
        target_price: targetPrice ? parseFloat(targetPrice) : null,
        memo: memo || null,
        tags: tags || null,
      });
      mutate();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">투자 의견 기록</p>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">투자 의견</label>
        <select
          value={opinion}
          onChange={(e) => setOpinion(e.target.value)}
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        >
          <option value="">선택</option>
          <option value="매수검토">매수 검토</option>
          <option value="보유">보유</option>
          <option value="관망">관망</option>
          <option value="매도검토">매도 검토</option>
        </select>
      </div>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">목표가 (USD)</label>
        <input
          type="number"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          placeholder="예: 180.00"
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        />
      </div>

      <div className="flex-1">
        <label className="text-xs text-muted-foreground mb-1 block">메모</label>
        <textarea
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          placeholder="투자 근거, 주요 리스크..."
          className="w-full h-full min-h-[120px] rounded border border-border bg-muted px-2 py-1.5 text-sm resize-none"
        />
      </div>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">태그</label>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="AI, 반도체, 성장주..."
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {saving ? "저장 중..." : "저장"}
      </button>
    </div>
  );
}
