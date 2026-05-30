"use client";
import { useState } from "react";
import useSWR from "swr";
import { alertsApi } from "@/lib/api";
import { useAlerts, formatConditionMsg } from "@/hooks/useAlerts";
import type { AlertConditionType, AlertEvent } from "@/lib/types";

const CONDITION_OPTIONS: { value: AlertConditionType; label: string; needsValue: boolean }[] = [
  { value: "price_above",      label: "가격 초과",      needsValue: true },
  { value: "price_below",      label: "가격 미만",      needsValue: true },
  { value: "rsi_above",        label: "RSI 과매수(>)", needsValue: true },
  { value: "rsi_below",        label: "RSI 과매도(<)", needsValue: true },
  { value: "ma_golden_cross",  label: "골든크로스",     needsValue: false },
  { value: "ma_dead_cross",    label: "데드크로스",     needsValue: false },
];

export function AlertPanel() {
  const { conditions, toasts, addAlert, removeAlert } = useAlerts();
  const { data: history = [] } = useSWR<AlertEvent[]>(
    "/api/alerts/events", alertsApi.events, { refreshInterval: 30_000 }
  );

  const [ticker, setTicker] = useState("");
  const [condType, setCondType] = useState<AlertConditionType>("price_above");
  const [condValue, setCondValue] = useState("");
  const [adding, setAdding] = useState(false);

  const selectedOpt = CONDITION_OPTIONS.find((o) => o.value === condType)!;

  async function handleAdd() {
    if (!ticker.trim()) return;
    if (selectedOpt.needsValue && (!condValue.trim() || isNaN(parseFloat(condValue)))) return;
    setAdding(true);
    try {
      await addAlert({
        ticker: ticker.trim().toUpperCase(),
        condition_type: condType,
        condition_value: selectedOpt.needsValue ? parseFloat(condValue) : null,
      });
      setTicker("");
      setCondValue("");
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      {/* 토스트 알림 */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id}
            className="bg-[var(--color-bg-secondary)] border border-[var(--color-primary)] px-3 py-2 text-[12px] font-data text-[var(--color-text-primary)] shadow-lg"
          >
            🔔 {t.message}
          </div>
        ))}
      </div>

      <div className="flex flex-col h-full overflow-hidden text-[12px] font-data">
        {/* 헤더 */}
        <div className="px-3 py-1.5 text-[11px] uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
          ALERTS
        </div>

        <div className="flex-1 overflow-auto p-3 flex flex-col gap-4">
          {/* 추가 폼 */}
          <div className="flex flex-col gap-1.5">
            <p className="text-[11px] uppercase tracking-widest text-[var(--color-text-secondary)]">NEW CONDITION</p>
            <div className="flex gap-1">
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="w-16 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1.5 py-1 text-[12px] font-data text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
              />
              <select
                value={condType}
                onChange={(e) => setCondType(e.target.value as AlertConditionType)}
                className="flex-1 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1 py-1 text-[12px] font-data text-[var(--color-text-primary)] outline-none"
              >
                {CONDITION_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            {selectedOpt.needsValue && (
              <input
                value={condValue}
                onChange={(e) => setCondValue(e.target.value)}
                placeholder="값 입력"
                type="number"
                className="w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1.5 py-1 text-[12px] font-data text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
              />
            )}
            <button
              onClick={handleAdd}
              disabled={adding || !ticker.trim() || (selectedOpt.needsValue && (!condValue.trim() || isNaN(parseFloat(condValue))))}
              className="w-full py-1 border border-[var(--color-primary)] text-[var(--color-primary)] text-[11px] uppercase tracking-widest hover:bg-[var(--color-primary)]/10 disabled:opacity-40 transition-colors"
            >
              {adding ? "추가 중…" : "+ 추가"}
            </button>
          </div>

          {/* 활성 조건 */}
          <div>
            <p className="text-[11px] uppercase tracking-widest text-[var(--color-text-secondary)] mb-1.5">ACTIVE</p>
            {conditions.length === 0 ? (
              <p className="text-[var(--color-text-muted)]">조건 없음</p>
            ) : (
              <div className="flex flex-col gap-1">
                {conditions.map((c) => (
                  <div key={c.id} className="flex items-center justify-between border border-[var(--color-border)] px-2 py-1">
                    <span className="text-[var(--color-text-primary)]">
                      {c.ticker}{" "}
                      <span className="text-[var(--color-text-secondary)]">
                        {CONDITION_OPTIONS.find((o) => o.value === c.condition_type)?.label}
                        {c.condition_value != null ? ` ${c.condition_value}` : ""}
                      </span>
                    </span>
                    <button
                      onClick={() => removeAlert(c.id)}
                      className="text-[#ff453a] hover:opacity-70 transition-opacity ml-2"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 알림 히스토리 */}
          <div>
            <p className="text-[11px] uppercase tracking-widest text-[var(--color-text-secondary)] mb-1.5">HISTORY</p>
            {history.length === 0 ? (
              <p className="text-[var(--color-text-muted)]">내역 없음</p>
            ) : (
              <div className="flex flex-col gap-1">
                {history.slice(0, 20).map((ev) => (
                  <div key={ev.id} className="flex items-start gap-2 border-b border-[var(--color-border)] pb-1">
                    <span className="text-[var(--color-text-muted)] shrink-0">
                      {new Date(ev.triggered_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className="text-[var(--color-text-secondary)]">{formatConditionMsg(ev)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
