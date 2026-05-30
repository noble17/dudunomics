"use client";
import { useState } from "react";
import useSWR from "swr";
import { tradesApi } from "@/lib/api";
import type { TradeIn } from "@/lib/types";

interface Props {
  filterTicker?: string;
}

function AddTradeModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState<TradeIn>({
    ticker: "", trade_type: "BUY", quantity: 0, price: 0,
    currency: "USD", traded_at: new Date().toISOString().slice(0, 10),
  });
  const [error, setError] = useState("");

  async function submit() {
    if (!form.ticker || form.quantity <= 0 || form.price <= 0) {
      setError("종목, 수량, 단가를 입력하세요.");
      return;
    }
    try {
      await tradesApi.create(form);
      onSave();
      onClose();
    } catch (e: any) {
      setError(e.message ?? "저장 실패");
    }
  }

  const inputCls = "bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] text-[var(--color-text-primary)] px-2 py-1 font-data text-[12px] w-full";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] p-4 w-72 font-data">
        <div className="text-[13px] uppercase tracking-widest text-[var(--color-primary)] mb-3">거래 추가</div>
        {error && <div className="text-error text-[12px] mb-2">{error}</div>}
        <div className="space-y-2">
          <div>
            <label className="text-[11px] text-[var(--color-text-muted)] uppercase block mb-0.5">Ticker</label>
            <input className={inputCls} value={form.ticker}
              onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))} />
          </div>
          <div className="flex gap-2">
            {(["BUY", "SELL"] as const).map(t => (
              <button key={t} onClick={() => setForm(f => ({ ...f, trade_type: t }))}
                className={`flex-1 py-1 text-[12px] border ${
                  form.trade_type === t
                    ? t === "BUY" ? "border-[#dc2e47] text-rise" : "border-[#3182f6] text-fall"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                }`}>
                {t}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[11px] text-[var(--color-text-muted)] uppercase block mb-0.5">수량</label>
              <input className={inputCls} type="number" value={form.quantity || ""}
                onChange={e => setForm(f => ({ ...f, quantity: parseFloat(e.target.value) || 0 }))} />
            </div>
            <div className="flex-1">
              <label className="text-[11px] text-[var(--color-text-muted)] uppercase block mb-0.5">단가</label>
              <input className={inputCls} type="number" value={form.price || ""}
                onChange={e => setForm(f => ({ ...f, price: parseFloat(e.target.value) || 0 }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[11px] text-[var(--color-text-muted)] uppercase block mb-0.5">통화</label>
              <select className={inputCls} value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value as "KRW" | "USD" }))}>
                <option value="USD">USD</option>
                <option value="KRW">KRW</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-[11px] text-[var(--color-text-muted)] uppercase block mb-0.5">날짜</label>
              <input className={inputCls} type="date" value={form.traded_at}
                onChange={e => setForm(f => ({ ...f, traded_at: e.target.value }))} />
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={submit}
            className="flex-1 py-1.5 text-[12px] bg-[var(--color-primary)] text-black font-data">
            저장
          </button>
          <button onClick={onClose}
            className="flex-1 py-1.5 text-[12px] border border-[var(--color-border)] text-[var(--color-text-muted)] font-data">
            취소
          </button>
        </div>
      </div>
    </div>
  );
}

export function TradeLogPanel({ filterTicker }: Props) {
  const [showModal, setShowModal] = useState(false);
  const { data: trades, mutate, isLoading } = useSWR(
    `/api/trades${filterTicker ? `?ticker=${filterTicker}` : ""}`,
    () => tradesApi.list(filterTicker),
    { refreshInterval: 30_000 }
  );

  async function handleDelete(id: number) {
    await tradesApi.delete(id);
    mutate();
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] shrink-0">
        <span className="text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)]">
          TRADE LOG{filterTicker ? ` — ${filterTicker}` : ""}
        </span>
        <button onClick={() => setShowModal(true)}
          className="text-[11px] font-data border border-[var(--color-primary)] text-[var(--color-primary)] px-2 py-0.5 hover:bg-[var(--color-primary)] hover:text-black transition-colors">
          + 거래 추가
        </button>
      </div>
      <div className="flex-1 overflow-auto">
        {isLoading && <div className="p-3 text-[12px] font-data text-[var(--color-text-muted)]">로딩 중…</div>}
        {!isLoading && !trades?.length && (
          <div className="p-3 text-[12px] font-data text-[var(--color-text-muted)]">거래 내역 없음</div>
        )}
        <div className="px-3">
          {(trades ?? []).map(trade => (
            <div key={trade.id}
              className="grid grid-cols-5 py-1.5 border-b border-[var(--color-border)] items-center text-[12px] font-data group">
              <span className="text-[var(--color-text-muted)] text-[11px]">{trade.traded_at}</span>
              <span className={trade.trade_type === "BUY" ? "text-rise" : "text-fall"}>
                {trade.trade_type}
              </span>
              <span className="text-[var(--color-text-primary)]">{trade.ticker}</span>
              <span className="text-[var(--color-text-secondary)] text-right">
                {trade.quantity}주 @{trade.price.toLocaleString()}
              </span>
              <div className="text-right">
                <button onClick={() => handleDelete(trade.id)}
                  className="opacity-0 group-hover:opacity-100 text-[11px] text-error hover:opacity-70 transition-opacity">
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
      {showModal && <AddTradeModal onClose={() => setShowModal(false)} onSave={() => mutate()} />}
    </div>
  );
}
