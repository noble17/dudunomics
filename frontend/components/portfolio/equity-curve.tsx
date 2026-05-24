// frontend/components/portfolio/equity-curve.tsx
"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { SnapshotHistory } from "@/lib/types";

interface Props {
  history: SnapshotHistory[];
  currency: "KRW" | "USD";
}

export function EquityCurve({ history, currency }: Props) {
  const sym = currency === "KRW" ? "₩" : "$";
  const data = [...history].reverse().map((h) => ({
    ts: h.ts.slice(0, 16).replace("T", " "),
    value: currency === "KRW" ? h.total_equity_krw : h.total_equity_usd,
  }));

  if (data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">스냅샷 없음 — 5분 후 자동 생성됩니다.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="ts" tick={{ fontSize: 11 }} tickCount={6} />
        <YAxis tickFormatter={(v) => `${sym}${(v / 1_000_000).toFixed(1)}M`} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => typeof v === "number" ? `${sym}${v.toLocaleString()}` : v} />
        <Area type="monotone" dataKey="value" stroke="#3b82f6" fill="url(#eq)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
