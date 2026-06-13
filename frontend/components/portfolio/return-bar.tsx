// frontend/components/portfolio/return-bar.tsx
"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import type { PortfolioRow } from "@/lib/types";

interface Props { rows: PortfolioRow[] }

const MONO = "var(--font-roboto-mono, 'Roboto Mono', monospace)";

export function ReturnBar({ rows }: Props) {
  const data = [...rows]
    .sort((a, b) => b.return_pct - a.return_pct)
    .map((r) => ({ name: r.name || r.ticker, value: r.return_pct }));

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-muted-foreground">
        보유 종목 없음
      </div>
    );
  }

  const height = Math.max(180, data.length * 32 + 40);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 8 }}>
        <XAxis
          type="number"
          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
          tick={{ fontSize: 10, fill: "var(--muted-foreground)", fontFamily: MONO }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={130}
          tick={{ fontSize: 10, fill: "var(--foreground)", fontFamily: MONO }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: string) => v.length > 16 ? v.slice(0, 15) + "…" : v}
        />
        <Tooltip
          cursor={{ fill: "var(--muted)", fillOpacity: 0.42 }}
          formatter={(v: unknown) => {
            const n = typeof v === "number" ? v : 0;
            return [`${n > 0 ? "+" : ""}${n.toFixed(2)}%`, "수익률"];
          }}
          contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 4, fontFamily: MONO, fontSize: 12, color: "var(--popover-foreground)" }}
          labelStyle={{ color: "var(--foreground)" }}
          itemStyle={{ color: "var(--foreground)" }}
        />
        <ReferenceLine x={0} stroke="var(--border)" strokeWidth={1.5} />
        <Bar dataKey="value" barSize={14} radius={0} label={{
          position: "right",
          formatter: (v: unknown) => { const n = typeof v === "number" ? v : 0; return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`; },
          style: { fontSize: 10, fontFamily: MONO, fill: "var(--foreground)" },
        }}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.value >= 0 ? "var(--rise)" : "var(--fall)"} fillOpacity={0.92} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
