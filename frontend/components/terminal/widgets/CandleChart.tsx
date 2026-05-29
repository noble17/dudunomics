"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import useSWR from "swr";
import { candlesApi } from "@/lib/api";
import type { CandleItem } from "@/lib/types";

type Period = "5D" | "1M" | "3M" | "6M" | "1Y";
const PERIODS: Period[] = ["5D", "1M", "3M", "6M", "1Y"];

interface Props {
  ticker: string;
}

export function CandleChart({ ticker }: Props) {
  const [period, setPeriod] = useState<Period>("3M");
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleSeriesRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeSeriesRef = useRef<any>(null);

  const { data, isLoading } = useSWR(
    ["candles", ticker, period],
    () => candlesApi.get(ticker, period),
    { dedupingInterval: 60_000 },
  );

  // 차트 마운트 / 언마운트
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#636366",
      },
      grid: {
        vertLines: { color: "#1a1a1a" },
        horzLines: { color: "#1a1a1a" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1a1a1a" },
      timeScale: { borderColor: "#1a1a1a", timeVisible: false },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#30d158",
      downColor: "#ff453a",
      borderUpColor: "#30d158",
      borderDownColor: "#ff453a",
      wickUpColor: "#30d158",
      wickDownColor: "#ff453a",
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const observer = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // 데이터 업데이트 (ticker 또는 period 변경 시)
  useEffect(() => {
    if (!data?.candles.length || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    candleSeriesRef.current.setData(
      data.candles.map((c: CandleItem) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    volumeSeriesRef.current.setData(
      data.candles.map((c: CandleItem) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(48,209,88,0.35)" : "rgba(255,69,58,0.35)",
      })),
    );

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  const candles = data?.candles ?? [];
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const change = last && prev ? last.close - prev.close : 0;
  const changePct = prev?.close ? (change / prev.close) * 100 : 0;
  const isUp = change >= 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 헤더 */}
      <div className="px-3 py-1.5 shrink-0 border-b border-[var(--color-border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">
            CHART
          </span>
          {last && (
            <>
              <span className="text-[11px] font-mono font-bold text-[var(--color-text-primary)]">
                {ticker}
              </span>
              <span className="text-[10px] font-mono text-[var(--color-text-primary)]">
                {last.close.toFixed(2)}
              </span>
              <span
                className={`text-[9px] font-mono ${
                  isUp ? "text-[#30d158]" : "text-[#ff453a]"
                }`}
              >
                {isUp ? "▲" : "▼"}
                {Math.abs(change).toFixed(2)} ({changePct.toFixed(2)}%)
              </span>
            </>
          )}
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-1.5 py-0.5 text-[9px] font-mono border transition-colors ${
                p === period
                  ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* 차트 */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && !data && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">로딩 중…</span>
          </div>
        )}
        {!isLoading && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">데이터 없음</span>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  );
}
