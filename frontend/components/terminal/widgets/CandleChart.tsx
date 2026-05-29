"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import useSWR from "swr";
import { candlesApi } from "@/lib/api";
import type { CandleItem, IndicatorsData } from "@/lib/types";

type Period = "5D" | "1M" | "3M" | "6M" | "1Y";
const PERIODS: Period[] = ["5D", "1M", "3M", "6M", "1Y"];

interface Props { ticker: string }

// scaleMargins: 각 구역이 전체 차트 높이에서 차지하는 위치
// top=0.56 → 상단 56%는 여백(다른 구역이 사용), bottom=0.28 → 하단 28%도 여백
// 결과적으로 56%~72% 구간에 렌더
const SCALE_MARGINS = {
  candle:   { top: 0.00, bottom: 0.47 },  // 0~53%
  volume:   { top: 0.55, bottom: 0.30 },  // 55~70%
  rsi:      { top: 0.72, bottom: 0.15 },  // 72~85%
  macd:     { top: 0.87, bottom: 0.00 },  // 87~100%
} as const;

const MA_COLORS: Record<string, string> = {
  "5":   "#ff9f0a",
  "20":  "#ffd60a",
  "60":  "#30d158",
  "120": "#64d2ff",
};

export function CandleChart({ ticker }: Props) {
  const [period, setPeriod] = useState<Period>("3M");
  const [showIndicators, setShowIndicators] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<Record<string, any>>({});

  const { data, isLoading } = useSWR(
    ["candles", ticker, period, showIndicators],
    () => candlesApi.get(ticker, period, showIndicators),
    { dedupingInterval: 60_000 },
  );

  // 차트 생성 (마운트 시 1회)
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

    // ── 캔들 (메인 우측 스케일) ──────────────────────────────
    chart.priceScale("right").applyOptions({ scaleMargins: SCALE_MARGINS.candle });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#30d158", downColor: "#ff453a",
      borderUpColor: "#30d158", borderDownColor: "#ff453a",
      wickUpColor: "#30d158", wickDownColor: "#ff453a",
    });

    // ── 볼륨 ─────────────────────────────────────────────────
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol_scale",
      color: "rgba(100,100,100,0.4)",
    });
    chart.priceScale("vol_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.volume,
    });

    // ── RSI ──────────────────────────────────────────────────
    const rsiSeries = chart.addLineSeries({
      priceScaleId: "rsi_scale",
      color: "#bf5af2",
      lineWidth: 1,
    });
    chart.priceScale("rsi_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.rsi,
    });

    // ── MACD ─────────────────────────────────────────────────
    const macdLineSeries = chart.addLineSeries({
      priceScaleId: "macd_scale",
      color: "#0a84ff",
      lineWidth: 1,
    });
    const macdSignalSeries = chart.addLineSeries({
      priceScaleId: "macd_scale",
      color: "#ff9f0a",
      lineWidth: 1,
    });
    const macdHistSeries = chart.addHistogramSeries({
      priceScaleId: "macd_scale",
    });
    chart.priceScale("macd_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.macd,
    });

    // ── MA (기본 포함) ────────────────────────────────────────
    const maSeriesMap: Record<string, ReturnType<typeof chart.addLineSeries>> = {};
    for (const [p, color] of Object.entries(MA_COLORS)) {
      maSeriesMap[p] = chart.addLineSeries({
        priceScaleId: "right",
        color,
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
      });
    }

    // ── 볼린저밴드 ────────────────────────────────────────────
    const bbUpper = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.6)",
      lineWidth: 1,
      lineStyle: 2, // dashed
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbMiddle = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.4)",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbLower = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.6)",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // ── VolumeMA ──────────────────────────────────────────────
    const volumeMaSeries = chart.addLineSeries({
      priceScaleId: "vol_scale",
      color: "#ff9f0a",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    seriesRef.current = {
      candle: candleSeries, volume: volumeSeries,
      rsi: rsiSeries, macdLine: macdLineSeries,
      macdSignal: macdSignalSeries, macdHist: macdHistSeries,
      bbUpper, bbMiddle, bbLower, volumeMa: volumeMaSeries,
      ...Object.fromEntries(Object.entries(maSeriesMap).map(([k, v]) => [`ma${k}`, v])),
    };

    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = {};
    };
  }, []);

  // 데이터 업데이트
  useEffect(() => {
    const s = seriesRef.current;
    if (!data?.candles.length || !s.candle) return;

    s.candle.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
    })));

    s.volume.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? "rgba(48,209,88,0.35)" : "rgba(255,69,58,0.35)",
    })));

    const ind: IndicatorsData | null | undefined = data.indicators;

    // MA
    for (const p of ["5", "20", "60", "120"]) {
      const pts = ind?.ma?.[p] ?? [];
      s[`ma${p}`]?.setData(pts);
    }

    // 볼린저
    s.bbUpper?.setData(ind?.bollinger?.upper ?? []);
    s.bbMiddle?.setData(ind?.bollinger?.middle ?? []);
    s.bbLower?.setData(ind?.bollinger?.lower ?? []);

    // RSI
    s.rsi?.setData(ind?.rsi ?? []);

    // MACD
    s.macdLine?.setData(ind?.macd?.macd ?? []);
    s.macdSignal?.setData(ind?.macd?.signal ?? []);
    s.macdHist?.setData(
      (ind?.macd?.histogram ?? []).map((pt) => ({
        time: pt.time,
        value: pt.value,
        color: pt.value >= 0 ? "rgba(48,209,88,0.6)" : "rgba(255,69,58,0.6)",
      }))
    );

    // VolumeMA
    s.volumeMa?.setData(ind?.volume_ma ?? []);

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
          <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">CHART</span>
          {last && (
            <>
              <span className="text-[11px] font-mono font-bold text-[var(--color-text-primary)]">{ticker}</span>
              <span className="text-[10px] font-mono text-[var(--color-text-primary)]">{last.close.toFixed(2)}</span>
              <span className={`text-[9px] font-mono ${isUp ? "text-[#30d158]" : "text-[#ff453a]"}`}>
                {isUp ? "▲" : "▼"}{Math.abs(change).toFixed(2)} ({changePct.toFixed(2)}%)
              </span>
            </>
          )}
        </div>
        <div className="flex gap-1 items-center">
          <button
            onClick={() => setShowIndicators((v) => !v)}
            className={`px-1.5 py-0.5 text-[9px] font-mono border transition-colors ${
              showIndicators
                ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
            }`}
          >
            지표
          </button>
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
