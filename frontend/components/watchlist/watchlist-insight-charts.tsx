"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { screenerApi } from "@/lib/api";
import type { FinancialDataPoint, FinancialsData, PriceChartData } from "@/lib/types";

interface Props {
  ticker: string;
  universe: string;
}

type EmaMode = "short" | "middle";
type FlowTab = "revenue" | "eps" | "roe";

const EMA_CONFIG = {
  close: { label: "주가", color: "var(--foreground)" },
  e5: { label: "5일", color: "#22c55e" },
  e20: { label: "20일", color: "#f59e0b" },
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

const FLOW_TABS: { key: FlowTab; label: string; title: string; unit: string }[] = [
  { key: "revenue", label: "매출액", title: "매출액", unit: "백만달러" },
  { key: "eps", label: "EPS 주당순이익", title: "EPS 주당순이익", unit: "달러" },
  { key: "roe", label: "ROE", title: "ROE", unit: "%" },
];

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getFullYear()).slice(2)}.${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatNumber(value: unknown, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function formatFlowValue(value: number, tab: FlowTab) {
  if (tab === "revenue") return value.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  if (tab === "eps") return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function formatMetric(value: number | null | undefined, suffix = "") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${suffix}`;
}

function pointYear(point: FinancialDataPoint) {
  const raw = point.year ?? point.period_end?.slice(0, 4) ?? point.period?.slice(0, 4);
  const year = Number(raw);
  return Number.isFinite(year) ? year : null;
}

function toTs(date: string) {
  return new Date(date).getTime();
}

function mergeEmaData(data: PriceChartData | undefined, mode: EmaMode) {
  if (!data) return [];
  const activeKeys = EMA_BY_MODE[mode];
  const maps = Object.fromEntries(
    activeKeys.map((key) => [key, new Map(data.ema[key].map((point) => [point.date, point.value]))]),
  ) as Record<keyof PriceChartData["ema"], Map<string, number>>;

  return data.ohlcv.map((point) => {
    const row: Record<string, number | string | null> = {
      date: point.date,
      ts: toTs(point.date),
      close: point.close,
    };
    for (const key of activeKeys) row[key] = maps[key].get(point.date) ?? null;
    return row;
  });
}

function annualPointDate(point: FinancialDataPoint) {
  const year = point.year ?? point.period_end?.slice(0, 4);
  if (!year) return null;
  return `${year}-12-31`;
}

function buildPriceEpsData(
  priceData: PriceChartData | undefined,
  epsPoints: FinancialDataPoint[] | undefined,
) {
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
    epsProjected: number | null;
  }[] = priceData.ohlcv.map((point) => {
    const matched = sourceActual.filter((eps) => eps.date <= point.date).at(-1);
    return {
      date: point.date,
      ts: toTs(point.date),
      price: point.close,
      eps: matched?.value ?? null,
      epsProjected: null as number | null,
    };
  });

  const latestActual = sourceActual.filter((eps) => eps.date <= lastPriceDate).at(-1);
  const lastPriceRow = rows.at(-1);
  if (latestActual && lastPriceRow) {
    lastPriceRow.epsProjected = latestActual.value;
  }

  for (const point of estimateEps.filter((eps) => eps.date > lastPriceDate)) {
    rows.push({
      date: point.date,
      ts: toTs(point.date),
      price: null,
      eps: null,
      epsProjected: point.value,
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
  const priceEpsData = useMemo(
    () => buildPriceEpsData(priceData, financials?.eps),
    [priceData, financials?.eps],
  );
  const activeEmaKeys = EMA_BY_MODE[emaMode];
  const hasProjectedEps = priceEpsData.some((point) => point.epsProjected != null);
  const epsUnavailable = Boolean(financialsError);

  return (
    <div className="min-w-0 space-y-4">
      {financials && <GrowthFlowCard data={financials} />}

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
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke={EMA_CONFIG.close.color}
                  strokeWidth={3}
                  strokeDasharray="2 8"
                  strokeOpacity={0.72}
                  dot={false}
                  name="close"
                  connectNulls={false}
                />
                {activeEmaKeys.map((key) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={EMA_CONFIG[key].color}
                    strokeWidth={2}
                    dot={false}
                    name={key}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <LegendRow items={[EMA_CONFIG.close, ...activeEmaKeys.map((key) => EMA_CONFIG[key])]} />
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
                    name === "price" ? "주가" : name === "epsProjected" ? "예상 EPS" : "EPS",
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="price" type="monotone" dataKey="price" stroke="#4f7cff" strokeWidth={2} dot={false} name="주가" connectNulls={false} />
                <Line yAxisId="eps" type="stepAfter" dataKey="eps" stroke="#22c55e" strokeWidth={2.2} dot={false} name="EPS" connectNulls />
                {hasProjectedEps && (
                  <Line
                    yAxisId="eps"
                    type="stepAfter"
                    dataKey="epsProjected"
                    stroke="#9ca3af"
                    strokeDasharray="10 7"
                    strokeOpacity={0.8}
                    strokeWidth={2}
                    dot={false}
                    name="예상 EPS"
                    connectNulls={false}
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
    </div>
  );
}

function GrowthFlowCard({ data }: { data: FinancialsData }) {
  const [activeTab, setActiveTab] = useState<FlowTab>("revenue");
  const tab = FLOW_TABS.find((item) => item.key === activeTab)!;
  const source = data.metrics.source ?? data.sources?.choicestock?.source;
  const sourceUrl = data.metrics.source_url ?? data.sources?.choicestock?.source_url;
  const sourceAsOf = data.metrics.as_of ?? data.sources?.choicestock?.as_of;
  const choicePoints = data.sources?.choicestock?.[activeTab] ?? [];
  const rawPoints = choicePoints.length ? choicePoints : data[activeTab] ?? [];
  const chartData = rawPoints
    .filter((point) => {
      const year = pointYear(point);
      return year == null || year >= 2024;
    })
    .slice(-5)
    .map((point) => {
    const label = point.period_end?.slice(0, 7).replace("-", ".") || point.year || point.period || "";
    return {
      name: label,
      value: point.value,
      isEstimate: point.is_estimate,
    };
  });
  const usingChoice = choicePoints.length > 0;

  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-heading text-xl font-semibold tracking-tight">성장성과 수익성 흐름은?</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {FLOW_TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setActiveTab(item.key)}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === item.key
                    ? "border-primary bg-primary text-primary-foreground shadow-sm"
                    : "border-border bg-background text-muted-foreground hover:border-primary/60 hover:text-foreground"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          {data.latest_report_date && <p>최근실적발표 {data.latest_report_date}</p>}
          <p>단위: {tab.unit}</p>
          <p>{usingChoice ? "초이스스탁 공개 데이터" : "공통 재무 데이터"}</p>
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between border-b border-border pb-3">
          <p className="text-lg font-semibold">{tab.title}</p>
          <span className="rounded-lg border border-border bg-background px-3 py-1 text-xs font-medium text-foreground">연간</span>
        </div>
        {chartData.length ? (
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={chartData} margin={{ top: 22, right: 10, left: 10, bottom: 4 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} opacity={0.55} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12, fill: "var(--foreground)", opacity: 0.72 }}
                axisLine={{ stroke: "var(--border)" }}
                tickLine={false}
                interval={0}
              />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip
                cursor={{ fill: "var(--muted)" }}
                contentStyle={TOOLTIP_STYLE}
                labelStyle={{ color: "var(--foreground)" }}
                itemStyle={{ color: "var(--foreground)" }}
                formatter={(value) => [`${formatFlowValue(Number(value), activeTab)} ${tab.unit}`, tab.title]}
                labelFormatter={(label) => String(label)}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={88}>
                <LabelList
                  dataKey="value"
                  position="top"
                  formatter={(value: unknown) => (
                    typeof value === "number" ? formatFlowValue(value, activeTab) : ""
                  )}
                  fill="var(--foreground)"
                  fontSize={12}
                  fontWeight={600}
                />
                {chartData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={
                      entry.value < 0
                        ? "rgba(96, 165, 250, 0.35)"
                        : entry.isEstimate
                          ? "rgba(148, 163, 184, 0.72)"
                          : "var(--primary)"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <ChartEmpty label="연간 재무 데이터가 없습니다." />
        )}
      </div>

      <div className="mt-5 border-t border-border">
        <div className="flex items-center justify-between border-b border-border py-3">
          <span className="text-base font-medium">시가총액</span>
          <span className="text-right font-data text-xl font-semibold">
            {formatMetric(data.metrics.market_cap_m)}
            <span className="ml-2 block text-xs font-normal text-muted-foreground">백만달러</span>
          </span>
        </div>
        <div className="grid gap-x-10 md:grid-cols-2">
          {[
            ["PER", data.metrics.trailing_pe],
            ["PER(F)", data.metrics.forward_pe],
            ["PEG", data.metrics.peg],
            ["PSR", data.metrics.price_to_sales],
          ].map(([label, value]) => (
            <div key={label as string} className="flex items-center justify-between border-b border-border py-3">
              <span className="text-base font-medium">{label}</span>
              <span className="font-data text-lg font-semibold">{formatMetric(value as number | null, "배")}</span>
            </div>
          ))}
        </div>
        {(source || sourceAsOf) && (
          <div className="pt-4 text-right text-xs text-muted-foreground">
            {sourceAsOf ? `${sourceAsOf} 기준` : ""}
            {source && (
              <>
                {" · 출처: "}
                {sourceUrl ? (
                  <a href={sourceUrl} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                    {source}
                  </a>
                ) : source}
              </>
            )}
          </div>
        )}
      </div>
    </section>
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
