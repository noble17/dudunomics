// frontend/components/backtest/backtest-result.tsx
"use client";

import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, Cell, LabelList,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { KpiCard } from "@/components/common/kpi-card";
import type { BacktestRunOut } from "@/lib/types";

const MONO = "var(--font-roboto-mono, 'Roboto Mono', monospace)";

const CHART_COLORS = [
  "#1375EC", "#DD3C44", "#0062DF", "#E67E22", "#27AE60",
  "#8E44AD", "#16A085", "#C0392B", "#2980B9", "#D35400",
];

function fmt(n: number, digits = 2) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

export function BacktestResult({ result }: { result: BacktestRunOut }) {
  const kpis = [
    { label: "총 수익률", value: fmt(result.total_return), pos: result.total_return >= 0 },
    ...(result.cagr != null ? [{ label: "CAGR", value: fmt(result.cagr), pos: result.cagr >= 0 }] : []),
    { label: "MDD",    value: `${result.mdd.toFixed(2)}%`, pos: false },
    { label: "Sharpe", value: result.sharpe.toFixed(2),     pos: result.sharpe >= 1 },
  ];

  return (
    <div className="space-y-4">
      {/* 종목 칩 */}
      {result.tickers && result.tickers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.tickers.map((t) => (
            <span key={t} className="border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* 경고 박스 */}
      {result.warnings && result.warnings.length > 0 && (
        <div className="border border-yellow-300 bg-yellow-50 px-4 py-3">
          <p className="mb-1 text-[11px] font-semibold text-yellow-800">주의</p>
          <ul className="space-y-0.5">
            {result.warnings.map((w, i) => (
              <li key={i} className="font-mono text-[11px] text-yellow-700">{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* KPI 카드 */}
      <div className={`grid gap-3 ${kpis.length === 4 ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3"}`}>
        {kpis.map(({ label, value, pos }) => (
          <KpiCard key={label} label={label} value={value} colored positive={pos} />
        ))}
      </div>

      {/* 차트 탭 */}
      <Tabs defaultValue="equity">
        <TabsList>
          <TabsTrigger value="equity">자산 곡선</TabsTrigger>
          {result.weights_history && result.weights_history.length > 0 && (
            <TabsTrigger value="weights">비중</TabsTrigger>
          )}
          {result.per_ticker_contribution && Object.keys(result.per_ticker_contribution).length > 0 && (
            <TabsTrigger value="contrib">기여도</TabsTrigger>
          )}
          {result.rebalance_log && result.rebalance_log.length > 0 && (
            <TabsTrigger value="log">리밸런싱 로그</TabsTrigger>
          )}
        </TabsList>

        {/* 자산 곡선 */}
        <TabsContent value="equity">
          <Card>
            <CardContent className="pt-5">
              <p className="mb-3 text-[11px] font-medium text-muted-foreground">자산 곡선</p>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                  <defs>
                    <linearGradient id="bt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#1375EC" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#1375EC" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="4 4" stroke="#EDEEF1" />
                  <XAxis dataKey="ts" tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }} tickCount={8} />
                  <YAxis
                    tickFormatter={(v) => `₩${(v / 1_000_000).toFixed(1)}M`}
                    tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }}
                  />
                  <Tooltip
                    formatter={(v: unknown) => typeof v === "number" ? [`₩${v.toLocaleString()}`] : [String(v)]}
                    contentStyle={{ background: "#FFFFFF", border: "1px solid #BEC1C6", borderRadius: 4, fontFamily: MONO, fontSize: 12 }}
                    labelStyle={{ color: "#1A2434" }}
                    itemStyle={{ color: "#1375EC" }}
                  />
                  <Area type="monotone" dataKey="equity" stroke="#1375EC" fill="url(#bt)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 비중 변화 */}
        {result.weights_history && result.weights_history.length > 0 && (() => {
          const allWeightKeys = Object.keys(result.weights_history[0]).filter((k) => k !== "ts");
          const cashKey = allWeightKeys.includes("cash_weight") ? "cash_weight" : null;
          const weightTickers = allWeightKeys.filter((k) => k !== "cash_weight");
          return (
            <TabsContent value="weights">
              <Card>
                <CardContent className="pt-5">
                  <p className="mb-3 text-[11px] font-medium text-muted-foreground">비중 변화</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={result.weights_history} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                      <CartesianGrid strokeDasharray="4 4" stroke="#EDEEF1" />
                      <XAxis dataKey="ts" tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }} tickCount={6} />
                      <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }} domain={[0, 1]} />
                      <Tooltip
                        formatter={(v: unknown, name: unknown) => [
                          typeof v === "number" ? `${(v * 100).toFixed(1)}%` : String(v),
                          String(name ?? ""),
                        ]}
                        contentStyle={{ background: "#FFFFFF", border: "1px solid #BEC1C6", borderRadius: 4, fontFamily: MONO, fontSize: 12 }}
                      />
                      {weightTickers.map((t, i) => (
                        <Area
                          key={t}
                          type="monotone"
                          dataKey={t}
                          stackId="1"
                          stroke={CHART_COLORS[i % CHART_COLORS.length]}
                          fill={CHART_COLORS[i % CHART_COLORS.length]}
                          fillOpacity={0.6}
                          dot={false}
                        />
                      ))}
                      {cashKey && (
                        <Area
                          key="cash_weight"
                          type="monotone"
                          dataKey="cash_weight"
                          stackId="1"
                          stroke="#9CA3AF"
                          fill="#9CA3AF"
                          fillOpacity={0.4}
                          dot={false}
                          name="현금"
                        />
                      )}
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </TabsContent>
          );
        })()}

        {/* 종목별 기여도 */}
        {result.per_ticker_contribution && Object.keys(result.per_ticker_contribution).length > 0 && (() => {
          const contribData = Object.entries(result.per_ticker_contribution)
            .map(([ticker, value]) => ({ ticker, value }))
            .sort((a, b) => b.value - a.value);
          return (
            <TabsContent value="contrib">
              <Card>
                <CardContent className="pt-5">
                  <p className="mb-3 text-[11px] font-medium text-muted-foreground">종목별 기여도 (원)</p>
                  <ResponsiveContainer width="100%" height={Math.max(160, contribData.length * 32)}>
                    <BarChart data={contribData} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 40 }}>
                      <CartesianGrid strokeDasharray="4 4" stroke="#EDEEF1" horizontal={false} />
                      <XAxis
                        type="number"
                        tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                        tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }}
                      />
                      <YAxis type="category" dataKey="ticker" tick={{ fontSize: 10, fill: "#333333", fontFamily: MONO }} width={52} />
                      <Tooltip
                        formatter={(v: unknown) => typeof v === "number" ? [`₩${v.toLocaleString()}`] : [String(v)]}
                        contentStyle={{ background: "#FFFFFF", border: "1px solid #BEC1C6", borderRadius: 4, fontFamily: MONO, fontSize: 12 }}
                      />
                      <Bar dataKey="value" radius={0}>
                        {contribData.map((entry, i) => (
                          <Cell key={i} fill={entry.value >= 0 ? "#DD3C44" : "#1375EC"} />
                        ))}
                        <LabelList
                          dataKey="value"
                          position="right"
                          formatter={(v: unknown) => typeof v === "number" ? `${(v / 10000).toFixed(0)}만` : ""}
                          style={{ fontSize: 10, fontFamily: MONO, fill: "#666666" }}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </TabsContent>
          );
        })()}

        {/* 리밸런싱 로그 */}
        {result.rebalance_log && result.rebalance_log.length > 0 && (
          <TabsContent value="log">
            <Card>
              <CardContent className="pt-5">
                <p className="mb-3 text-[11px] font-medium text-muted-foreground">리밸런싱 로그</p>
                <div className="overflow-x-auto">
                  <table className="w-full font-mono text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="pb-1 pr-4">날짜</th>
                        <th className="pb-1 pr-4">종류</th>
                        <th className="pb-1 pr-4">내용</th>
                        <th className="pb-1 text-right">포트폴리오 가치</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.rebalance_log.map((row, i) => {
                        const type = String(row.type ?? "");
                        const date = String(row.date ?? row.ts ?? "");
                        if (type === "dead_cross") {
                          const ticker = String(row.ticker ?? row.tickers ?? "");
                          const amount = typeof row.amount === "number" ? `₩${row.amount.toLocaleString()}` : String(row.amount ?? "");
                          return (
                            <tr key={i} className="border-b border-border">
                              <td className="py-1 pr-4 text-muted-foreground">{date}</td>
                              <td className="py-1 pr-4">데드크로스</td>
                              <td className="py-1 pr-4 text-[#DD3C44]">{ticker} 청산</td>
                              <td className="py-1 text-right">{amount}</td>
                            </tr>
                          );
                        }
                        const holdings = Array.isArray(row.holdings) ? row.holdings.join(", ") : String(row.holdings ?? "");
                        const dropped = Array.isArray(row.sma_dropped) ? row.sma_dropped.join(", ") : String(row.sma_dropped ?? "");
                        const portfolioValue = typeof row.portfolio_value === "number" ? `₩${row.portfolio_value.toLocaleString()}` : String(row.portfolio_value ?? "");
                        return (
                          <tr key={i} className="border-b border-border">
                            <td className="py-1 pr-4 text-muted-foreground">{date}</td>
                            <td className="py-1 pr-4">월간</td>
                            <td className="py-1 pr-4">
                              {holdings && <span>{holdings}</span>}
                              {dropped && <span className="ml-2 text-muted-foreground">(탈락: {dropped})</span>}
                            </td>
                            <td className="py-1 text-right">{portfolioValue}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      <p className="text-right font-mono text-xs text-muted-foreground">Run ID: {result.id}</p>
    </div>
  );
}
