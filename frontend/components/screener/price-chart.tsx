"use client";

import { useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { PriceChartData } from "@/lib/types";

interface Props {
  data: PriceChartData;
}

type Tab = "ema" | "price_eps";

function fmtDateYYMM(dateStr: string): string {
  const d = new Date(dateStr);
  return `${String(d.getFullYear()).slice(2)}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function last3Months<T extends { date: string }>(points: T[]): T[] {
  if (points.length === 0) return points;
  const latest = new Date(points[points.length - 1].date);
  const cutoff = new Date(latest);
  cutoff.setMonth(cutoff.getMonth() - 3);
  return points.filter((p) => new Date(p.date) >= cutoff);
}

export function PriceChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("ema");
  const [emaRange, setEmaRange] = useState<"short" | "full">("short");

  const e5Points = emaRange === "short" ? last3Months(data.ema.e5) : data.ema.e5;
  const dateSet = new Set(e5Points.map((p) => p.date));

  const emaChartData = data.ohlcv
    .filter((p) => dateSet.has(p.date))
    .map((p) => {
      const e5 = data.ema.e5.find((e) => e.date === p.date);
      const e20 = data.ema.e20.find((e) => e.date === p.date);
      const e60 = data.ema.e60.find((e) => e.date === p.date);
      return { date: p.date, e5: e5?.value, e20: e20?.value, e60: e60?.value };
    });

  // 분기 EPS를 날짜순으로 정렬 (오래된 것 먼저)
  const sortedEps = [...data.quarterly_eps].sort((a, b) => a.date.localeCompare(b.date));

  const priceEpsChartData = data.ohlcv.map((p) => {
    const eps = sortedEps.filter((e) => e.date <= p.date).at(-1);
    return { date: p.date, price: p.close, eps: eps?.eps };
  });

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
                dataKey="date"
                tickFormatter={fmtDateYYMM}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false} width={50}
              />
              <Tooltip
                formatter={(v) => typeof v === "number" ? `$${v.toFixed(2)}` : String(v)}
                labelFormatter={(label) => typeof label === "string" ? fmtDateYYMM(label) : String(label)}
                contentStyle={{ fontSize: 11, borderRadius: 6 }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11 }}
                formatter={(v: string) => ({ e5: "EMA5", e20: "EMA20", e60: "EMA60" }[v] ?? v)}
              />
              <Line type="monotone" dataKey="e5"  stroke="#22c55e" dot={false} strokeWidth={1.5} name="e5" />
              <Line type="monotone" dataKey="e20" stroke="#9ca3af" dot={false} strokeWidth={1.5} name="e20" />
              <Line type="monotone" dataKey="e60" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="e60" />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}

      {activeTab === "price_eps" && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={priceEpsChartData} margin={{ top: 4, right: 50, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDateYYMM}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false} tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis yAxisId="price" domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={50} />
            <YAxis yAxisId="eps" orientation="right" domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 6 }}
              formatter={(v, name) => {
                const val = typeof v === "number" ? `$${v.toFixed(2)}` : String(v);
                return [val, name === "price" ? "주가" : "EPS"];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(v: string) => (v === "price" ? "● 주가" : "● 주당순이익")}
            />
            <Line yAxisId="price" type="monotone"  dataKey="price" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="price" />
            <Line yAxisId="eps"   type="stepAfter" dataKey="eps"   stroke="#22c55e" dot={false} strokeWidth={2}   name="eps" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
