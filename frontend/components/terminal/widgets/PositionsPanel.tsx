"use client";
import { useState } from "react";
import useSWR from "swr";
import { RefreshCw } from "lucide-react";
import { portfolioApi, holdingsApi } from "@/lib/api";

interface Props {
  onTickerSelect?: (ticker: string) => void;
  selectedTicker?: string;
}

interface SyncToast {
  id: number;
  message: string;
  isError: boolean;
}

let _toastId = 0;

export function PositionsPanel({ onTickerSelect, selectedTicker }: Props) {
  const { data: snapshot, isLoading, mutate } = useSWR(
    "/api/portfolio/current",
    portfolioApi.current,
    { refreshInterval: 30_000 }
  );
  const [syncing, setSyncing] = useState(false);
  const [toasts, setToasts] = useState<SyncToast[]>([]);

  function showToast(message: string, isError = false) {
    const id = ++_toastId;
    setToasts((prev) => [...prev, { id, message, isError }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await holdingsApi.syncFromKis();
      if (result.errors.length > 0) {
        showToast(`동기화 오류: ${result.errors[0]}`, true);
      } else {
        showToast(`KIS 동기화 완료 — 추가 ${result.added}개, 수정 ${result.updated}개`);
      }
      mutate();
    } catch {
      showToast("KIS 동기화 실패", true);
    } finally {
      setSyncing(false);
    }
  }

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );
  if (!snapshot?.rows.length) return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0 flex items-center justify-between">
        <span>POSITIONS</span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[8px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={9} className={syncing ? "animate-spin" : ""} />
          KIS
        </button>
      </div>
      <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">보유 종목 없음</div>
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-3 py-2 text-[10px] font-mono shadow-lg border ${
              t.isError
                ? "bg-[var(--color-bg-secondary)] border-red-500 text-red-400"
                : "bg-[var(--color-bg-secondary)] border-[var(--color-primary)] text-[var(--color-text-primary)]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );

  const realizedPnl = (snapshot as any).realized_pnl_krw ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 토스트 */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-3 py-2 text-[10px] font-mono shadow-lg border ${
              t.isError
                ? "bg-[var(--color-bg-secondary)] border-red-500 text-red-400"
                : "bg-[var(--color-bg-secondary)] border-[var(--color-primary)] text-[var(--color-text-primary)]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>

      {/* 헤더 */}
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0 flex items-center justify-between">
        <span>POSITIONS</span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[8px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={9} className={syncing ? "animate-spin" : ""} />
          KIS
        </button>
      </div>

      {/* 종목 리스트 */}
      <div className="flex-1 overflow-auto">
        <div className="px-3 py-1">
          <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
            <span>Ticker</span>
            <span className="text-right">수익률</span>
            <span className="text-right">평가액</span>
          </div>
          {snapshot.rows.map((row) => (
            <div
              key={row.ticker}
              onClick={() => onTickerSelect?.(row.ticker)}
              className={`grid grid-cols-3 py-1 border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] text-[10px] font-mono ${
                selectedTicker === row.ticker ? "bg-[var(--color-bg-tertiary)]" : ""
              }`}
            >
              <span className="text-[var(--color-text-primary)]">{row.ticker}</span>
              <span className={`text-right ${row.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                {row.return_pct >= 0 ? "+" : ""}{row.return_pct.toFixed(1)}%
              </span>
              <span className="text-right text-[var(--color-text-secondary)]">
                ₩{(row.market_value_krw / 1_000_000).toFixed(1)}M
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 하단 요약 */}
      <div className="px-3 py-2 border-t border-[var(--color-border)] shrink-0 space-y-0.5">
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">총 평가</span>
          <span className="text-[var(--color-text-primary)]">
            ₩{(snapshot.total_equity_krw / 1_000_000).toFixed(1)}M
          </span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">실현 손익</span>
          <span className={realizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
            {realizedPnl >= 0 ? "+" : ""}₩{(realizedPnl / 10_000).toFixed(0)}만
          </span>
        </div>
      </div>
    </div>
  );
}
