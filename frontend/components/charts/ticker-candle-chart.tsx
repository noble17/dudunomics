"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type Time,
} from "lightweight-charts";
import useSWR from "swr";
import { candlesApi } from "@/lib/api";
import type { CandleItem, IndicatorsData } from "@/lib/types";

type Period = "5D" | "1M" | "3M" | "6M" | "1Y";
const PERIODS: Period[] = ["5D", "1M", "3M", "6M", "1Y"];
type IndicatorKey = "ma" | "bollinger" | "rsi" | "macd" | "volumeMa";
const MA_PERIODS = ["20", "50", "120", "200"] as const;
const LEGACY_MA_PERIODS = ["5", "60"] as const;

type ChartColors = {
  bg: string;
  grid: string;
  axisLine: string;
  text: string;
  up: string;
  down: string;
  brand: string;
  brandAlt: string;
  ma: Record<(typeof MA_PERIODS)[number], string>;
};

const FALLBACK_CHART_COLORS: ChartColors = {
  bg: "#101013",
  grid: "rgba(214,224,239,0.09)",
  axisLine: "rgba(214,224,239,0.09)",
  text: "rgba(242,242,255,0.47)",
  up: "#dc2e47",
  down: "#3182f6",
  brand: "#3182f6",
  brandAlt: "#4391ff",
  ma: {
    "20": "#ff9f0a",
    "50": "#ffd60a",
    "120": "#3182f6",
    "200": "#22d3ee",
  },
};

interface Props {
  ticker: string;
  defaultPeriod?: Period;
  defaultShowIndicators?: boolean;
  refreshKey?: string | number;
  heightClassName?: string;
}

const TOGGLE_LABELS: Record<IndicatorKey, string> = {
  ma: "SMA",
  bollinger: "Bollinger",
  rsi: "RSI",
  macd: "MACD",
  volumeMa: "Vol MA",
};

export function TickerCandleChart({
  ticker,
  defaultPeriod = "3M",
  defaultShowIndicators = false,
  refreshKey = 0,
  heightClassName = "h-full",
}: Props) {
  const [period, setPeriod] = useState<Period>(defaultPeriod);
  const [hoveredTime, setHoveredTime] = useState<string | null>(null);
  const [chartColors, setChartColors] = useState<ChartColors>(FALLBACK_CHART_COLORS);
  const [indicatorOptions, setIndicatorOptions] = useState<Record<IndicatorKey, boolean>>({
    ma: true,
    bollinger: defaultShowIndicators,
    rsi: defaultShowIndicators,
    macd: defaultShowIndicators,
    volumeMa: defaultShowIndicators,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<Record<string, any>>({});

  const indicatorsEnabled = Object.values(indicatorOptions).some(Boolean);
  const legendItems = [
    { label: "일봉 캔들", color: chartColors.up, note: "종가 기준" },
    { label: "거래량", color: "rgba(139,149,161,0.65)", note: "막대" },
    { label: "SMA20", color: chartColors.ma["20"], group: "ma" },
    { label: "SMA50", color: chartColors.ma["50"], group: "ma" },
    { label: "SMA120", color: chartColors.ma["120"], group: "ma" },
    { label: "SMA200", color: chartColors.ma["200"], group: "ma" },
    { label: "Bollinger", color: "rgba(100, 210, 255, 0.7)", group: "bollinger" },
    { label: "RSI 14", color: "#bf5af2", group: "rsi" },
    { label: "MACD", color: chartColors.brand, group: "macd" },
    { label: "Signal", color: "#ff9f0a", group: "macd" },
    { label: "Vol MA20", color: "#ff9f0a", group: "volumeMa" },
  ] as const;
  const { data, isLoading } = useSWR(
    ["candles", ticker, period, indicatorsEnabled, refreshKey],
    () => candlesApi.get(ticker, period, indicatorsEnabled),
    { dedupingInterval: 60_000 },
  );

  useEffect(() => {
    setChartColors(readChartColors());

    const observer = new MutationObserver(() => setChartColors(readChartColors()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => observer.disconnect();
  }, []);

  // 차트 생성 (마운트 시 1회)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: chartColors.bg },
        textColor: chartColors.text,
        panes: {
          enableResize: true,
          separatorColor: chartColors.axisLine,
          separatorHoverColor: chartColors.brand,
        },
      },
      grid: {
        vertLines: { color: chartColors.grid },
        horzLines: { color: chartColors.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: chartColors.axisLine },
      timeScale: { borderColor: chartColors.axisLine, timeVisible: false },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: chartColors.up, downColor: chartColors.down,
      borderUpColor: chartColors.up, borderDownColor: chartColors.down,
      wickUpColor: chartColors.up, wickDownColor: chartColors.down,
    }, 0);

    // ── 볼륨 ─────────────────────────────────────────────────
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      color: "rgba(100,100,100,0.4)",
      lastValueVisible: false,
      priceLineVisible: false,
    }, 1);
    chart.priceScale("right", 1).applyOptions({ borderVisible: false, visible: true });

    // ── RSI ──────────────────────────────────────────────────
    const rsiSeries = chart.addSeries(LineSeries, {
      color: "#bf5af2",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 2);
    chart.priceScale("right", 2).applyOptions({ borderVisible: false, visible: true });
    rsiSeries.createPriceLine({ price: 70, color: chartColors.up, lineStyle: 2, lineWidth: 1, axisLabelVisible: false, title: "70" });
    rsiSeries.createPriceLine({ price: 30, color: chartColors.down, lineStyle: 2, lineWidth: 1, axisLabelVisible: false, title: "30" });

    // ── MACD ─────────────────────────────────────────────────
    const macdLineSeries = chart.addSeries(LineSeries, {
      color: chartColors.brand,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 3);
    const macdSignalSeries = chart.addSeries(LineSeries, {
      color: "#ff9f0a",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 3);
    const macdHistSeries = chart.addSeries(HistogramSeries, {
      lastValueVisible: false,
      priceLineVisible: false,
    }, 3);
    chart.priceScale("right", 3).applyOptions({ borderVisible: false, visible: true });

    // ── MA (기본 포함) ────────────────────────────────────────
    const maSeriesMap: Record<string, unknown> = {};
    for (const [p, color] of Object.entries(chartColors.ma)) {
      maSeriesMap[p] = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        lastValueVisible: false,
        priceLineVisible: false,
      }, 0);
    }

    // ── 볼린저밴드 ────────────────────────────────────────────
    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(100, 210, 255, 0.4)",
      lineWidth: 1,
      lineStyle: 2, // dashed
      lastValueVisible: false,
      priceLineVisible: false,
    }, 0);
    const bbMiddle = chart.addSeries(LineSeries, {
      color: "rgba(100, 210, 255, 0.7)",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 0);
    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(100, 210, 255, 0.4)",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 0);

    // ── VolumeMA ──────────────────────────────────────────────
    const volumeMaSeries = chart.addSeries(LineSeries, {
      color: "#ff9f0a",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    }, 1);

    seriesRef.current = {
      candle: candleSeries, volume: volumeSeries,
      rsi: rsiSeries, macdLine: macdLineSeries,
      macdSignal: macdSignalSeries, macdHist: macdHistSeries,
      bbUpper, bbMiddle, bbLower, volumeMa: volumeMaSeries,
      ...Object.fromEntries(Object.entries(maSeriesMap).map(([k, v]) => [`ma${k}`, v])),
    };

    chartRef.current = chart;
    const crosshairHandler = (param: { time?: Time }) => {
      setHoveredTime(timeToString(param.time));
    };
    chart.subscribeCrosshairMove(crosshairHandler);

    const observer = new ResizeObserver(() => {
      chart.resize(container.clientWidth, container.clientHeight);
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.unsubscribeCrosshairMove(crosshairHandler);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = {};
    };
  }, [chartColors]);

  // 데이터 업데이트
  useEffect(() => {
    const s = seriesRef.current;
    if (!data?.candles.length || !s.candle) return;

    s.candle.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
    })));

    s.volume.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? withOpacity(chartColors.up, 0.38) : withOpacity(chartColors.down, 0.38),
    })));

    const ind: IndicatorsData | null | undefined = data.indicators;

    // MA
    const showMa = indicatorOptions.ma;
    for (const p of LEGACY_MA_PERIODS) {
      s[`ma${p}`]?.setData([]);
    }
    for (const p of MA_PERIODS) {
      const pts = ind?.ma?.[p] ?? [];
      s[`ma${p}`]?.setData(showMa ? pts : []);
    }

    // 볼린저
    s.bbUpper?.setData(indicatorOptions.bollinger ? ind?.bollinger?.upper ?? [] : []);
    s.bbMiddle?.setData(indicatorOptions.bollinger ? ind?.bollinger?.middle ?? [] : []);
    s.bbLower?.setData(indicatorOptions.bollinger ? ind?.bollinger?.lower ?? [] : []);

    // RSI
    s.rsi?.setData(indicatorOptions.rsi ? ind?.rsi ?? [] : []);

    // MACD
    s.macdLine?.setData(indicatorOptions.macd ? ind?.macd?.macd ?? [] : []);
    s.macdSignal?.setData(indicatorOptions.macd ? ind?.macd?.signal ?? [] : []);
    s.macdHist?.setData(
      (indicatorOptions.macd ? ind?.macd?.histogram ?? [] : []).map((pt) => ({
        time: pt.time,
        value: pt.value,
        color: pt.value >= 0 ? withOpacity(chartColors.up, 0.65) : withOpacity(chartColors.down, 0.65),
      }))
    );

    // VolumeMA
    s.volumeMa?.setData(indicatorOptions.volumeMa ? ind?.volume_ma ?? [] : []);

    chartRef.current?.timeScale().fitContent();
  }, [data, indicatorOptions, chartColors]);

  useEffect(() => {
    if (!chartRef.current) return;
    applyPaneLayout(chartRef.current, indicatorOptions);
  }, [indicatorOptions]);

  const candles = data?.candles ?? [];
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const displayTime = hoveredTime ?? last?.time ?? null;
  const displayCandle = findCandle(candles, displayTime) ?? last;
  const displayCandleTime = displayCandle?.time ?? null;
  const displayPrev = displayCandle ? previousCandle(candles, displayCandle.time) : prev;
  const change = displayCandle && displayPrev ? displayCandle.close - displayPrev.close : 0;
  const changePct = displayPrev?.close ? (change / displayPrev.close) * 100 : 0;
  const isUp = change >= 0;
  const indicators = data?.indicators;
  const latestSma = {
    "20": valueAt(indicators?.ma?.["20"], displayCandleTime),
    "50": valueAt(indicators?.ma?.["50"], displayCandleTime),
    "120": valueAt(indicators?.ma?.["120"], displayCandleTime),
    "200": valueAt(indicators?.ma?.["200"], displayCandleTime),
  };
  const latestRsi = valueAt(indicators?.rsi, displayCandleTime);
  const latestMacd = valueAt(indicators?.macd?.macd, displayCandleTime);
  const latestMacdSignal = valueAt(indicators?.macd?.signal, displayCandleTime);
  const latestMacdHist = valueAt(indicators?.macd?.histogram, displayCandleTime);
  const latestVolumeMa = valueAt(indicators?.volume_ma, displayCandleTime);
  const toggleIndicator = (key: IndicatorKey) => {
    setIndicatorOptions((current) => ({ ...current, [key]: !current[key] }));
  };
  const allOptionalEnabled = indicatorOptions.bollinger && indicatorOptions.rsi && indicatorOptions.macd && indicatorOptions.volumeMa;

  return (
    <div className={`flex flex-col overflow-hidden ${heightClassName}`}>
      {/* 헤더 */}
      <div className="shrink-0 border-b border-[var(--color-border)] px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)]">차트</span>
          {last && (
            <>
              <span className="text-[13px] font-data font-bold text-[var(--color-text-primary)]">{ticker}</span>
              <span className="text-[12px] font-data text-[var(--color-text-primary)]">{formatNumber(displayCandle?.close, 2)}</span>
              <span className={`text-[11px] font-data ${isUp ? "text-rise" : "text-fall"}`}>
                {isUp ? "▲" : "▼"}{Math.abs(change).toFixed(2)} ({changePct.toFixed(2)}%)
              </span>
              <span className="text-[10px] font-data text-[var(--color-text-muted)]">
                {displayCandleTime ?? "-"} · 일봉 · 완료된 종가 기준
              </span>
            </>
          )}
          </div>
          <div className="flex flex-wrap items-center gap-1">
            {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-1.5 py-0.5 text-[11px] font-data border transition-colors ${
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
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[10px] font-data uppercase tracking-widest text-[var(--color-text-muted)]">
            Indicators
          </span>
          <button
            type="button"
            onClick={() =>
              setIndicatorOptions((current) => ({
                ...current,
                bollinger: !allOptionalEnabled,
                rsi: !allOptionalEnabled,
                macd: !allOptionalEnabled,
                volumeMa: !allOptionalEnabled,
              }))
            }
            className={`rounded border px-1.5 py-0.5 text-[10px] font-data transition-colors ${
              allOptionalEnabled
                ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
            }`}
          >
            보조 전체
          </button>
          {(Object.keys(TOGGLE_LABELS) as IndicatorKey[]).map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={indicatorOptions[key]}
              onClick={() => toggleIndicator(key)}
              className={`rounded border px-1.5 py-0.5 text-[10px] font-data transition-colors ${
                indicatorOptions[key]
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
              }`}
            >
              {TOGGLE_LABELS[key]}
            </button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {legendItems.filter((item) => isLegendVisible(item, indicatorOptions)).map((item) => (
            <span key={item.label} className="inline-flex items-center gap-1 text-[10px] font-data text-[var(--color-text-muted)]">
              <span className="h-1.5 w-3 rounded-full" style={{ backgroundColor: item.color }} />
              <span>{item.label}</span>
              {"note" in item && <span className="opacity-70">· {item.note}</span>}
            </span>
          ))}
        </div>
        <div className="mt-2 grid gap-2 text-[10px] font-data text-[var(--color-text-muted)] md:grid-cols-2 xl:grid-cols-4">
          {indicatorOptions.ma && (
            <MetricGroup title="PRICE / SMA">
              {Object.entries(latestSma).map(([periodValue, value]) => (
                <span key={periodValue} className="inline-flex items-center gap-1">
                  <Dot color={chartColors.ma[periodValue as keyof ChartColors["ma"]]} />
                  SMA{periodValue} <strong className="font-normal text-[var(--color-text-primary)]">{formatNumber(value)}</strong>
                  {displayCandle && value != null && (
                    <em className={displayCandle.close >= value ? "not-italic text-rise" : "not-italic text-fall"}>
                      {formatPct((displayCandle.close / value - 1) * 100)}
                    </em>
                  )}
                </span>
              ))}
            </MetricGroup>
          )}
          <MetricGroup title="VOLUME">
            <span>거래량 <strong className="font-normal text-[var(--color-text-primary)]">{formatCompact(displayCandle?.volume)}</strong></span>
            {indicatorOptions.volumeMa && (
              <span className="inline-flex items-center gap-1">
                <Dot color="#ff9f0a" />
                Vol MA20 <strong className="font-normal text-[var(--color-text-primary)]">{formatCompact(latestVolumeMa)}</strong>
              </span>
            )}
          </MetricGroup>
          {indicatorOptions.rsi && (
            <MetricGroup title="RSI">
              <span className="inline-flex items-center gap-1">
                <Dot color="#bf5af2" />
                RSI 14 <strong className="font-normal text-[var(--color-text-primary)]">{formatNumber(latestRsi, 2)}</strong>
              </span>
              <span>{rsiLabel(latestRsi)}</span>
            </MetricGroup>
          )}
          {indicatorOptions.macd && (
            <MetricGroup title="MACD">
              <span className="inline-flex items-center gap-1">
                <Dot color={chartColors.brand} />
                MACD <strong className="font-normal text-[var(--color-text-primary)]">{formatNumber(latestMacd, 2)}</strong>
              </span>
              <span className="inline-flex items-center gap-1">
                <Dot color="#ff9f0a" />
                Signal <strong className="font-normal text-[var(--color-text-primary)]">{formatNumber(latestMacdSignal, 2)}</strong>
              </span>
              <span>
                Hist <strong className={latestMacdHist != null && latestMacdHist >= 0 ? "font-normal text-rise" : "font-normal text-fall"}>
                  {formatSigned(latestMacdHist)}
                </strong>
              </span>
            </MetricGroup>
          )}
        </div>
      </div>

      {/* 차트 */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && !data && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-data text-[var(--color-text-muted)]">로딩 중…</span>
          </div>
        )}
        {!isLoading && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-data text-[var(--color-text-muted)]">데이터 없음</span>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  );
}

function latestValue(points?: { value: number }[] | null) {
  if (!points?.length) return null;
  return points[points.length - 1]?.value ?? null;
}

function valueAt(points?: { time: string; value: number }[] | null, time?: string | null) {
  if (!points?.length) return null;
  if (!time) return latestValue(points);
  return points.find((point) => point.time === time)?.value ?? latestValue(points);
}

function findCandle(candles: CandleItem[], time?: string | null) {
  if (!time) return null;
  return candles.find((candle) => candle.time === time) ?? null;
}

function previousCandle(candles: CandleItem[], time: string) {
  const index = candles.findIndex((candle) => candle.time === time);
  return index > 0 ? candles[index - 1] : null;
}

function timeToString(time?: Time) {
  if (!time) return null;
  if (typeof time === "string") return time;
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10);
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function formatCompact(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "-";
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function formatPct(value: number) {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatSigned(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "-";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

function rsiLabel(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "RSI 데이터 없음";
  if (value >= 80) return "극단 과열";
  if (value >= 70) return "과열 주의";
  if (value <= 30) return "과매도";
  return "중립";
}

function isLegendVisible(
  item: { label: string; color: string; note?: string; group?: IndicatorKey },
  indicatorOptions: Record<IndicatorKey, boolean>,
) {
  return !item.group || indicatorOptions[item.group];
}

function Dot({ color }: { color: string }) {
  return <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />;
}

function MetricGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded border border-[var(--color-border)] bg-[var(--color-bg)]/50 px-2 py-1.5">
      <p className="mb-1 text-[9px] uppercase tracking-widest text-[var(--color-primary)]">{title}</p>
      <div className="flex flex-wrap gap-x-2 gap-y-1">{children}</div>
    </div>
  );
}

function applyPaneLayout(
  chart: ReturnType<typeof createChart>,
  indicatorOptions: Record<IndicatorKey, boolean>,
) {
  const panes = chart.panes();
  panes[0]?.setStretchFactor(5);
  panes[1]?.setStretchFactor(1.15);
  panes[2]?.setStretchFactor(indicatorOptions.rsi ? 1 : 0.01);
  panes[3]?.setStretchFactor(indicatorOptions.macd ? 1 : 0.01);
}

function readChartColors(): ChartColors {
  if (typeof window === "undefined") return FALLBACK_CHART_COLORS;

  const styles = getComputedStyle(document.documentElement);
  const css = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
  const card = css("--card", FALLBACK_CHART_COLORS.bg);
  const border = css("--border", FALLBACK_CHART_COLORS.grid);
  const muted = css("--muted-foreground", FALLBACK_CHART_COLORS.text);
  const primary = css("--primary", FALLBACK_CHART_COLORS.brand);

  return {
    bg: card,
    grid: border,
    axisLine: border,
    text: muted,
    up: css("--rise", FALLBACK_CHART_COLORS.up),
    down: css("--fall", FALLBACK_CHART_COLORS.down),
    brand: primary,
    brandAlt: css("--color-connected", FALLBACK_CHART_COLORS.brandAlt),
    ma: {
      "20": "#ff9f0a",
      "50": "#facc15",
      "120": primary,
      "200": "#22d3ee",
    },
  };
}

function withOpacity(color: string, opacity: number) {
  const trimmed = color.trim();
  if (trimmed.startsWith("rgba(")) {
    return trimmed.replace(/rgba\(([^)]+),\s*[\d.]+\)/, `rgba($1, ${opacity})`);
  }
  if (trimmed.startsWith("rgb(")) {
    return trimmed.replace("rgb(", "rgba(").replace(")", `, ${opacity})`);
  }
  if (/^#[\da-f]{6}$/i.test(trimmed)) {
    const r = parseInt(trimmed.slice(1, 3), 16);
    const g = parseInt(trimmed.slice(3, 5), 16);
    const b = parseInt(trimmed.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return trimmed;
}
