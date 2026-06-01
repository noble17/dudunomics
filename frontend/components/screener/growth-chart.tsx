"use client";

import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { FinancialsData } from "@/lib/types";

interface Props {
  data: FinancialsData;
}

type Tab = "revenue" | "eps" | "roe";
type Period = "annual" | "quarterly";

const TABS: { key: Tab; label: string; unit: string }[] = [
  { key: "revenue", label: "매출액", unit: "백만달러" },
  { key: "eps",     label: "EPS 주당순이익", unit: "달러" },
  { key: "roe",     label: "ROE", unit: "%" },
];

function fmtValue(value: number, tab: Tab): string {
  if (tab === "revenue") return value.toLocaleString();
  if (tab === "eps") return `${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

function fmtYoy(yoy: number): string {
  return `${yoy >= 0 ? "+" : ""}${yoy.toFixed(2)}%`;
}

interface TooltipPayload {
  value: number;
  payload: { name: string; value: number; is_estimate: boolean; yoy?: number };
}

function CustomTooltip({
  active, payload, label, tab, unit,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  tab: Tab;
  unit: string;
}) {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  const yoy = entry.payload.yoy;
  const isEst = entry.payload.is_estimate;
  return (
    <div style={{
      backgroundColor: "#202025",
      border: "1px solid rgba(214,224,239,0.09)",
      borderRadius: 6,
      fontSize: 11,
      color: "rgba(242,246,255,0.9)",
      padding: "6px 10px",
      lineHeight: 1.6,
    }}>
      <p>{label}{isEst ? " (예상)" : ""}</p>
      <p>{TABS.find(t => t.key === tab)?.label}: {fmtValue(entry.payload.value, tab)}{tab !== "roe" ? ` ${unit}` : ""}</p>
      {yoy !== undefined && (
        <p style={{ color: yoy >= 0 ? "#ef4444" : "#60a5fa" }}>전년대비 {fmtYoy(yoy)}</p>
      )}
    </div>
  );
}

export function GrowthChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("revenue");
  const [period, setPeriod] = useState<Period>("annual");
  const tabCfg = TABS.find((t) => t.key === activeTab)!;

  const annualPoints = data[activeTab] ?? [];
  const quarterlyPoints = data.quarterly?.[activeTab] ?? [];
  const isQuarterly = period === "quarterly";

  const rawPoints = isQuarterly
    ? quarterlyPoints.map((p) => ({ name: p.period, value: p.value, is_estimate: p.is_estimate }))
    : annualPoints.map((p) => ({ name: p.period_end || p.year || "", value: p.value, is_estimate: p.is_estimate }));

  const chartData = rawPoints.map((p, i) => {
    const prev = rawPoints[i - 1];
    const yoy = prev && prev.value !== 0
      ? ((p.value - prev.value) / Math.abs(prev.value)) * 100
      : undefined;
    return { ...p, yoy };
  });

  const hasQuarterly = quarterlyPoints.length > 0;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        성장성과 수익성 흐름은?
      </p>

      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <div className="flex gap-1">
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
      </div>

      <div className="flex justify-between items-center text-xs text-muted-foreground mb-2">
        <div className="flex gap-1">
          {(["annual", "quarterly"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              disabled={p === "quarterly" && !hasQuarterly}
              className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                period === p
                  ? "bg-muted-foreground text-background"
                  : "text-muted-foreground hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed"
              }`}
            >
              {p === "annual" ? "연간" : "분기"}
            </button>
          ))}
        </div>
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
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              content={<CustomTooltip tab={activeTab} unit={tabCfg.unit} />}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={40}>
              <LabelList
                dataKey="value"
                content={(props: Record<string, unknown>) => {
                  const x = props.x as number;
                  const y = props.y as number;
                  const width = props.width as number;
                  const height = props.height as number;
                  const value = props.value as number;
                  const label = typeof value === "number" ? fmtValue(value, activeTab) : String(value ?? "");
                  const cx = x + width / 2;
                  // 음수 막대: 막대 안쪽 상단(zero-line 바로 아래)에 배치해 x축 레이블과 겹침 방지
                  const cy = value < 0 ? y + 12 : y - 4;
                  return (
                    <text x={cx} y={cy} textAnchor="middle" fontSize={9} fill="var(--muted-foreground)">
                      {label}
                    </text>
                  );
                }}
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
