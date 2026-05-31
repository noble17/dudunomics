"use client";

import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { FinancialsData, FinancialDataPoint } from "@/lib/types";

interface Props {
  data: FinancialsData;
}

type Tab = "revenue" | "eps" | "roe";

const TABS: { key: Tab; label: string; unit: string }[] = [
  { key: "revenue", label: "매출액", unit: "백만달러" },
  { key: "eps",     label: "EPS 주당순이익", unit: "달러" },
  { key: "roe",     label: "ROE", unit: "%" },
];

function fmtValue(value: number, tab: Tab): string {
  if (tab === "revenue") {
    return value >= 1_000 ? `${(value / 1_000).toFixed(0)}B` : `${value.toFixed(0)}M`;
  }
  if (tab === "eps") return `$${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

export function GrowthChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("revenue");
  const tabCfg = TABS.find((t) => t.key === activeTab)!;
  const points: FinancialDataPoint[] = data[activeTab] ?? [];

  const chartData = points.map((p) => ({
    name: p.period_end || p.year,
    value: p.value,
    is_estimate: p.is_estimate,
  }));

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        성장성과 수익성 흐름은?
      </p>

      <div className="flex gap-1 mb-3">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              activeTab === t.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex justify-between text-xs text-muted-foreground mb-2">
        <span className="bg-blue-100 text-blue-700 rounded px-2 py-0.5 text-[10px]">연간</span>
        {data.latest_report_date && (
          <span>최근실적발표 {data.latest_report_date} · 단위: {tabCfg.unit}</span>
        )}
      </div>

      {chartData.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
          데이터 없음
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              formatter={(v) => typeof v === "number" ? fmtValue(v, activeTab) : String(v)}
              contentStyle={{ fontSize: 11, borderRadius: 6 }}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={40}>
              <LabelList
                dataKey="value"
                position="top"
                formatter={(v: unknown) => typeof v === "number" ? fmtValue(v, activeTab) : String(v ?? "")}
                style={{ fontSize: 10, fill: "var(--foreground)" }}
              />
              {chartData.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.is_estimate ? "var(--muted)" : "var(--color-chart-1, #3b82f6)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs border-t border-border pt-3">
        {data.metrics.market_cap_m !== null && (
          <div className="col-span-2 flex justify-between">
            <span className="text-muted-foreground">시가총액</span>
            <span className="font-mono font-semibold">
              {data.metrics.market_cap_m?.toLocaleString()} 백만달러
            </span>
          </div>
        )}
        {[
          { label: "PER", value: data.metrics.trailing_pe, suffix: "배" },
          { label: "PER(F)", value: data.metrics.forward_pe, suffix: "배" },
          { label: "PEG", value: data.metrics.peg, suffix: "배" },
          { label: "PSR", value: data.metrics.price_to_sales, suffix: "배" },
        ].map(({ label, value, suffix }) => (
          <div key={label} className="flex justify-between">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono">{value !== null ? `${value?.toFixed(2)}${suffix}` : "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
