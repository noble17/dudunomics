// frontend/components/backtest/backtest-result.tsx
"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import type { BacktestRunOut } from "@/lib/types";

export function BacktestResult({ result }: { result: BacktestRunOut }) {
  const kpis = [
    { label: "총 수익률", value: `${result.total_return >= 0 ? "+" : ""}${result.total_return.toFixed(2)}%`, pos: result.total_return >= 0 },
    { label: "MDD", value: `${result.mdd.toFixed(2)}%`, pos: false },
    { label: "Sharpe", value: result.sharpe.toFixed(2), pos: result.sharpe >= 1 },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {kpis.map(({ label, value, pos }) => (
          <Card key={label}>
            <CardContent className="pt-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className={`mt-1 text-2xl font-bold ${pos ? "text-emerald-600" : "text-rose-600"}`}>{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="pt-4">
          <p className="mb-2 text-sm font-medium">자산 곡선</p>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
              <defs>
                <linearGradient id="bt" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="ts" tick={{ fontSize: 10 }} tickCount={8} />
              <YAxis tickFormatter={(v) => `₩${(v / 1_000_000).toFixed(1)}M`} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: unknown) => typeof v === "number" ? [`₩${v.toLocaleString()}`] : [String(v)]} />
              <Area type="monotone" dataKey="equity" stroke="#10b981" fill="url(#bt)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <p className="text-right text-xs text-muted-foreground">Run ID: {result.id}</p>
    </div>
  );
}
