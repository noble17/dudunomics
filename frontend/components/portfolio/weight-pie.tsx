// frontend/components/portfolio/weight-pie.tsx
"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { PortfolioRow } from "@/lib/types";

const COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"];

interface Props { rows: PortfolioRow[] }

export function WeightPie({ rows }: Props) {
  const data = rows.map((r) => ({ name: r.ticker, value: r.weight_pct }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
             outerRadius={90} innerRadius={50} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v) => typeof v === "number" ? `${v.toFixed(1)}%` : v} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
