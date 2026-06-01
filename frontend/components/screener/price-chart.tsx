"use client";

import { useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { FinancialDataPoint, PriceChartData } from "@/lib/types";

interface Props {
  data: PriceChartData;
  annualEps?: FinancialDataPoint[];
}

type Tab = "ema" | "price_eps";

const TOOLTIP_STYLE = {
  backgroundColor: "#202025",
  border: "1px solid rgba(214,224,239,0.09)",
  borderRadius: 6,
  fontSize: 11,
  color: "rgba(242,246,255,0.9)",
};
const ITEM_STYLE = { color: "rgba(242,246,255,0.9)" };

const EMA_LABELS: Record<string, string> = { e5: "5일", e20: "20일", e60: "60일" };
const EMA_LEGEND_ITEMS = [
  { key: "e5", label: "5일", color: "#22c55e" },
  { key: "e20", label: "20일", color: "#9ca3af" },
  { key: "e60", label: "60일", color: "#3b82f6" },
];

function fmtDateYYMMDD(dateStr: string): string {
  const d = new Date(dateStr);
  return [
    String(d.getFullYear()).slice(2),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join(".");
}

function last3Months<T extends { date: string }>(points: T[]): T[] {
  if (points.length === 0) return points;
  const latest = new Date(points[points.length - 1].date);
  const cutoff = new Date(latest);
  cutoff.setMonth(cutoff.getMonth() - 3);
  return points.filter((p) => new Date(p.date) >= cutoff);
}

export function PriceChart({ data, annualEps }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("ema");
  const [emaRange, setEmaRange] = useState<"short" | "full">("short");

  // EMA 차트 — Map 기반으로 O(1) 조회, ts(타임스탬프)를 x축에 사용해 모든 날짜 tooltip 활성화
  const e5Points = emaRange === "short" ? last3Months(data.ema.e5) : data.ema.e5;
  const e20Map = new Map(data.ema.e20.map((p) => [p.date, p.value]));
  const e60Map = new Map(data.ema.e60.map((p) => [p.date, p.value]));

  const emaChartData = e5Points.map((p) => ({
    date: p.date,
    ts: new Date(p.date).getTime(),
    e5: p.value,
    e20: e20Map.get(p.date),
    e60: e60Map.get(p.date),
  }));

  // 주가&EPS: 분기 EPS 우선, 없으면 연간 EPS fallback (is_estimate 제외)
  const sortedQuarterlyEps = [...data.quarterly_eps].sort((a, b) => a.date.localeCompare(b.date));
  const hasQuarterlyEps = sortedQuarterlyEps.length > 0;

  const annualEpsActual = (annualEps ?? [])
    .filter((e) => !e.is_estimate)
    .map((e) => ({ date: `${e.year ?? e.period_end ?? ""}-12-31`, eps: e.value }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const annualEpsEst = (annualEps ?? [])
    .filter((e) => e.is_estimate)
    .map((e) => ({ date: `${e.year ?? e.period_end ?? ""}-12-31`, eps: e.value }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const hasAnnualEps = annualEpsActual.length > 0;
  const hasEpsData = hasQuarterlyEps || hasAnnualEps;
  const hasEpsEst = annualEpsEst.length > 0;

  // 실제 주가 기간 + 미래 예상 EPS 기간을 합산
  const lastActualDate = data.ohlcv.at(-1)?.date ?? "";
  const futureEpsDates: string[] = hasEpsEst
    ? annualEpsEst
        .filter((e) => e.date > lastActualDate)
        .map((e) => e.date)
    : [];

  const priceEpsChartData = [
    ...data.ohlcv.map((p) => {
      let eps: number | null = null;
      if (hasQuarterlyEps) {
        const match = sortedQuarterlyEps.filter((e) => e.date <= p.date).at(-1);
        eps = match?.eps ?? null;
      } else if (hasAnnualEps) {
        const match = annualEpsActual.filter((e) => e.date <= p.date).at(-1);
        eps = match?.eps ?? null;
      }
      return { date: p.date, price: p.close, eps, eps_est: null as number | null };
    }),
    ...futureEpsDates.map((date) => {
      const match = annualEpsEst.filter((e) => e.date <= date).at(-1);
      return { date, price: null as number | null, eps: null as number | null, eps_est: match?.eps ?? null };
    }),
  ];

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        주가 흐름은?
      </p>

      <div className="flex gap-1 mb-3">
        {(["ema", "price_eps"] as Tab[]).map((key) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              activeTab === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {key === "ema" ? "지수이동평균선(EMA)" : "주가&EPS"}
          </button>
        ))}
      </div>

      {activeTab === "ema" && (
        <>
          <div className="flex gap-1 mb-2">
            {(["short", "full"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setEmaRange(r)}
                className={`px-2 py-0.5 text-[10px] rounded ${
                  emaRange === r ? "bg-muted-foreground text-background" : "text-muted-foreground"
                }`}
              >
                {r === "short" ? "단기(3M)" : "중기(전체)"}
              </button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={emaChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="ts"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(ts: number) => fmtDateYYMMDD(new Date(ts).toISOString().slice(0, 10))}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false}
                interval="preserveStartEnd"
                scale="time"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false} width={50}
              />
              <Tooltip
                formatter={(v, name) => [
                  typeof v === "number" ? `$${v.toFixed(2)}` : String(v),
                  EMA_LABELS[String(name)] ?? String(name),
                ]}
                labelFormatter={(label) => fmtDateYYMMDD(new Date(label as number).toISOString().slice(0, 10))}
                contentStyle={TOOLTIP_STYLE}
                itemStyle={ITEM_STYLE}
                itemSorter={(item) => -(item.value as number)}
              />
              {/* e5 → e20 → e60 순서로 선언 (레이어 순서) */}
              <Line type="monotone" dataKey="e5"  stroke="#22c55e" dot={false} strokeWidth={1.5} name="e5" />
              <Line type="monotone" dataKey="e20" stroke="#9ca3af" dot={false} strokeWidth={1.5} name="e20" />
              <Line type="monotone" dataKey="e60" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="e60" />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-1 flex justify-center gap-4 text-xs text-muted-foreground">
            {EMA_LEGEND_ITEMS.map((item) => (
              <div key={item.key} className="flex items-center gap-1.5">
                <span className="relative flex h-2.5 w-4 items-center">
                  <span className="h-px w-full" style={{ backgroundColor: item.color }} />
                  <span
                    className="absolute left-1/2 h-2 w-2 -translate-x-1/2 rounded-full border-2 bg-background"
                    style={{ borderColor: item.color }}
                  />
                </span>
                <span style={{ color: item.color }}>{item.label}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {activeTab === "price_eps" && (
        <>
          {!hasEpsData && (
            <p className="text-[10px] text-muted-foreground mb-1">EPS 데이터 없음 — 주가만 표시</p>
          )}
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={priceEpsChartData} margin={{ top: 4, right: hasEpsData ? 50 : 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDateYYMMDD}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                yAxisId="price"
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "#3b82f6" }}
                axisLine={false} tickLine={false} width={50}
              />
              {hasEpsData && (
                <YAxis
                  yAxisId="eps"
                  orientation="right"
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 10, fill: "#22c55e" }}
                  axisLine={false} tickLine={false} width={40}
                  tickFormatter={(v) => `$${typeof v === "number" ? v.toFixed(1) : v}`}
                />
              )}
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                itemStyle={ITEM_STYLE}
                formatter={(v, name) => {
                  const val = typeof v === "number" ? `$${v.toFixed(2)}` : String(v);
                  return [val, name === "price" ? "주가" : "주당순이익"];
                }}
                labelFormatter={(label) => typeof label === "string" ? fmtDateYYMMDD(label) : String(label)}
              />
              <Legend
                wrapperStyle={{ fontSize: 11 }}
                formatter={(v: string) => v === "price" ? "● 주가" : v === "eps" ? "● 주당순이익" : "⋯ 예상 EPS (추정)"}
              />
              <Line yAxisId="price" type="monotone" dataKey="price" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="price" connectNulls />
              {hasEpsData && (
                <Line yAxisId="eps" type="stepAfter" dataKey="eps" stroke="#22c55e" dot={false} strokeWidth={2} name="eps" connectNulls />
              )}
              {hasEpsEst && (
                <Line yAxisId="eps" type="stepAfter" dataKey="eps_est" stroke="#fbbf24" dot={false} strokeWidth={2} strokeDasharray="5 4" name="eps_est" connectNulls />
              )}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
