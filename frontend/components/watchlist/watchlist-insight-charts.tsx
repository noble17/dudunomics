"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { screenerApi } from "@/lib/api";
import type { FinancialDataPoint, PriceChartData } from "@/lib/types";

interface Props {
  ticker: string;
  universe: string;
}

type EmaMode = "short" | "middle";

const EMA_CONFIG = {
  e5: { label: "5일", color: "#22c55e" },
  e20: { label: "20일", color: "#a8b2c1" },
  e60: { label: "60일", color: "#4f7cff" },
  e120: { label: "120일", color: "#16b8d9" },
} as const;

const EMA_BY_MODE: Record<EmaMode, (keyof PriceChartData["ema"])[]> = {
  short: ["e5", "e20", "e60"],
  middle: ["e20", "e60", "e120"],
};

const TOOLTIP_STYLE = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  color: "var(--foreground)",
  fontSize: 11,
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getFullYear()).slice(2)}.${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatNumber(value: unknown, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function toTs(date: string) {
  return new Date(date).getTime();
}

function mergeEmaData(data: PriceChartData | undefined, mode: EmaMode) {
  if (!data) return [];
  const activeKeys = EMA_BY_MODE[mode];
  const baseKey = activeKeys[0];
  const maps = Object.fromEntries(
    activeKeys.map((key) => [key, new Map(data.ema[key].map((point) => [point.date, point.value]))]),
  ) as Record<keyof PriceChartData["ema"], Map<string, number>>;

  return data.ema[baseKey].map((point) => {
    const row: Record<string, number | string> = { date: point.date, ts: toTs(point.date) };
    for (const key of activeKeys) row[key] = maps[key].get(point.date) ?? point.value;
    return row;
  });
}

function annualPointDate(point: FinancialDataPoint) {
  const year = point.year ?? point.period_end?.slice(0, 4);
  if (!year) return null;
  return `${year}-12-31`;
}

function buildPriceEpsData(priceData: PriceChartData | undefined, epsPoints: FinancialDataPoint[] | undefined) {
  if (!priceData) return [];
  const actualEps = (epsPoints ?? [])
    .filter((point) => !point.is_estimate)
    .map((point) => ({ date: annualPointDate(point), value: point.value }))
    .filter((point): point is { date: string; value: number } => Boolean(point.date))
    .sort((a, b) => a.date.localeCompare(b.date));
  const estimateEps = (epsPoints ?? [])
    .filter((point) => point.is_estimate)
    .map((point) => ({ date: annualPointDate(point), value: point.value }))
    .filter((point): point is { date: string; value: number } => Boolean(point.date))
    .sort((a, b) => a.date.localeCompare(b.date));

  const quarterly = [...priceData.quarterly_eps].sort((a, b) => a.date.localeCompare(b.date));
  const sourceActual = quarterly.length
    ? quarterly.map((point) => ({ date: point.date, value: point.eps }))
    : actualEps;
  const lastPriceDate = priceData.ohlcv.at(-1)?.date ?? "";

  const rows: {
    date: string;
    ts: number;
    price: number | null;
    eps: number | null;
    epsEstimate: number | null;
  }[] = priceData.ohlcv.map((point) => {
    const matched = sourceActual.filter((eps) => eps.date <= point.date).at(-1);
    return {
      date: point.date,
      ts: toTs(point.date),
      price: point.close,
      eps: matched?.value ?? null,
      epsEstimate: null as number | null,
    };
  });

  for (const point of estimateEps.filter((eps) => eps.date > lastPriceDate)) {
    rows.push({
      date: point.date,
      ts: toTs(point.date),
      price: null,
      eps: null,
      epsEstimate: point.value,
    });
  }

  return rows.sort((a, b) => a.ts - b.ts);
}

export function WatchlistInsightCharts({ ticker, universe }: Props) {
  const [emaMode, setEmaMode] = useState<EmaMode>("short");
  const { data: priceData, error: priceError, isLoading: priceLoading } = useSWR(
    `/api/screener/ticker/${ticker}/price-chart`,
    () => screenerApi.priceChart(ticker),
  );
  const { data: financials, error: financialsError } = useSWR(
    `/api/screener/ticker/${ticker}/financials?universe=${universe}`,
    () => screenerApi.financials(ticker, universe),
  );
  const emaData = useMemo(() => mergeEmaData(priceData, emaMode), [priceData, emaMode]);
  const priceEpsData = useMemo(() => buildPriceEpsData(priceData, financials?.eps), [priceData, financials?.eps]);
  const activeEmaKeys = EMA_BY_MODE[emaMode];
  const hasEstimate = priceEpsData.some((point) => point.epsEstimate != null);
  const epsUnavailable = Boolean(financialsError);

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-2">
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">지수이동평균선(EMA)</p>
            <p className="mt-1 text-xs text-muted-foreground">단기선과 장기선의 기울기와 교차를 따로 확인합니다.</p>
          </div>
          <div className="flex rounded-lg border border-border bg-muted/35 p-1">
            {(["short", "middle"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setEmaMode(mode)}
                className={`rounded-md px-3 py-1 text-xs ${
                  emaMode === mode ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {mode === "short" ? "단기" : "중기"}
              </button>
            ))}
          </div>
        </div>

        {priceLoading ? (
          <ChartEmpty label="EMA 차트를 불러오는 중입니다." />
        ) : priceError ? (
          <ChartEmpty label="EMA 데이터를 불러오지 못했습니다." tone="error" />
        ) : emaData.length ? (
          <>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={emaData} margin={{ top: 12, right: 10, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} opacity={0.6} />
                <XAxis
                  dataKey="ts"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(value) => formatDate(new Date(value).toISOString())}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={42}
                />
                <YAxis
                  orientation="right"
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={(value) => formatDate(new Date(value as number).toISOString())}
                  formatter={(value, name) => [
                    formatNumber(value),
                    EMA_CONFIG[name as keyof typeof EMA_CONFIG]?.label ?? String(name),
                  ]}
                />
                {activeEmaKeys.map((key) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={EMA_CONFIG[key].color}
                    strokeWidth={2.4}
                    dot={false}
                    name={key}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <LegendRow items={activeEmaKeys.map((key) => EMA_CONFIG[key])} />
          </>
        ) : (
          <ChartEmpty label="EMA 데이터가 없습니다. 데이터 보강 후 다시 확인해 주세요." />
        )}
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">주가 & EPS</p>
            <p className="mt-1 text-xs text-muted-foreground">주가는 실제 구간까지만, EPS는 예상치까지 이어서 표시합니다.</p>
          </div>
          <span className="font-data text-[10px] text-muted-foreground">단위: 주가 / EPS</span>
        </div>

        {priceLoading ? (
          <ChartEmpty label="주가와 EPS를 불러오는 중입니다." />
        ) : priceError ? (
          <ChartEmpty label="주가 데이터를 불러오지 못했습니다." tone="error" />
        ) : priceEpsData.length ? (
          <>
            {epsUnavailable && (
              <p className="mb-2 rounded border border-border bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground">
                EPS 데이터가 없어 주가 중심으로 표시합니다.
              </p>
            )}
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={priceEpsData} margin={{ top: 12, right: 10, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} opacity={0.6} />
                <XAxis
                  dataKey="ts"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(value) => formatDate(new Date(value).toISOString())}
                  tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={42}
                />
                <YAxis
                  yAxisId="price"
                  tick={{ fontSize: 11, fill: "#4f7cff" }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                  domain={["auto", "auto"]}
                />
                <YAxis
                  yAxisId="eps"
                  orientation="right"
                  tick={{ fontSize: 11, fill: "#22c55e" }}
                  tickLine={false}
                  axisLine={false}
                  width={42}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={(value) => formatDate(new Date(value as number).toISOString())}
                  formatter={(value, name) => [
                    formatNumber(value),
                    name === "price" ? "주가" : name === "epsEstimate" ? "예상 EPS" : "EPS",
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="price" type="monotone" dataKey="price" stroke="#4f7cff" strokeWidth={2} dot={false} name="주가" connectNulls={false} />
                <Line yAxisId="eps" type="stepAfter" dataKey="eps" stroke="#22c55e" strokeWidth={2.2} dot={false} name="EPS" connectNulls />
                {hasEstimate && (
                  <Line
                    yAxisId="eps"
                    type="stepAfter"
                    dataKey="epsEstimate"
                    stroke="#a8b2c1"
                    strokeDasharray="6 5"
                    strokeWidth={2.2}
                    dot={false}
                    name="예상 EPS"
                    connectNulls
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </>
        ) : (
          <ChartEmpty label="표시할 주가 데이터가 없습니다. 데이터 보강 후 다시 확인해 주세요." />
        )}
      </section>
    </div>
  );
}

function ChartEmpty({ label, tone = "muted" }: { label: string; tone?: "muted" | "error" }) {
  return (
    <div
      className={`flex h-[280px] items-center justify-center rounded-lg border px-4 text-center text-xs ${
        tone === "error"
          ? "border-loss/30 bg-loss/5 text-loss"
          : "border-border bg-background/40 text-muted-foreground"
      }`}
    >
      {label}
    </div>
  );
}

function LegendRow({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="mt-2 flex justify-center gap-5 text-xs text-muted-foreground">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-5 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
