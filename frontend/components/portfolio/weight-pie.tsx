// frontend/components/portfolio/weight-pie.tsx
"use client";

import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { PortfolioRow } from "@/lib/types";

const COLORS = [
  "#1375EC",
  "#DD3C44",
  "#003597",
  "#666666",
  "#BEC1C6",
  "rgba(19,117,236,0.55)",
  "rgba(221,60,68,0.55)",
  "rgba(0,53,151,0.55)",
];

type Tab = "전체" | "국장" | "미장" | "섹터";
const TABS: Tab[] = ["전체", "국장", "미장", "섹터"];

function formatMan(krw: number) {
  if (krw >= 1_000_000_000) return `${(krw / 1_000_000_000).toFixed(1)}억`;
  return `${Math.round(krw / 10_000).toLocaleString("ko-KR")}만`;
}

interface ChartItem { name: string; value: number; krw: number; color: string }

const CASH_COLOR = "#8B9CB6";

interface Props { rows: PortfolioRow[]; cashKrw?: number }

export function WeightPie({ rows, cashKrw = 0 }: Props) {
  const [tab, setTab] = useState<Tab>("전체");

  const filtered =
    tab === "국장" ? rows.filter((r) => r.currency === "KRW") :
    tab === "미장" ? rows.filter((r) => r.currency === "USD") :
    rows;

  let data: ChartItem[];

  if (tab === "섹터") {
    const sectorMap = new Map<string, number>();
    for (const r of rows) {
      const key = r.sector?.trim() || "기타";
      sectorMap.set(key, (sectorMap.get(key) ?? 0) + r.market_value_krw);
    }
    const sectorTotal = rows.reduce((s, r) => s + r.market_value_krw, 0);
    data = Array.from(sectorMap.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, krw], i) => ({
        name,
        value: sectorTotal > 0 ? (krw / sectorTotal) * 100 : 0,
        krw,
        color: COLORS[i % COLORS.length],
      }));
  } else {
    const stockTotal = filtered.reduce((s, r) => s + r.market_value_krw, 0);
    const totalWithCash = tab === "전체" ? stockTotal + cashKrw : stockTotal;
    data = [...filtered]
      .sort((a, b) => b.market_value_krw - a.market_value_krw)
      .map((r, i) => ({
        name: r.name || r.ticker,
        value: totalWithCash > 0 ? (r.market_value_krw / totalWithCash) * 100 : 0,
        krw: r.market_value_krw,
        color: COLORS[i % COLORS.length],
      }));
    if (tab === "전체" && cashKrw > 0) {
      data.push({
        name: "현금",
        value: totalWithCash > 0 ? (cashKrw / totalWithCash) * 100 : 0,
        krw: cashKrw,
        color: CASH_COLOR,
      });
    }
  }

  const chartTotal = data.reduce((s, d) => s + d.krw, 0);
  const isEmpty = data.length === 0;

  return (
    <div>
      {/* 탭 */}
      <div className="mb-3 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1 text-xs font-medium border transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-border text-muted-foreground hover:border-primary/50"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isEmpty ? (
        <div className="flex h-48 items-center justify-center text-xs text-muted-foreground">
          보유 종목 없음
        </div>
      ) : (
        <>
          {/* 도넛 + 중앙 레이블 */}
          <div className="relative">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={data}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={85}
                  innerRadius={52}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {data.map((d, i) => (
                    <Cell key={i} fill={d.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => typeof v === "number" ? `${v.toFixed(1)}%` : v}
                  contentStyle={{ background: "#FFFFFF", border: "1px solid #BEC1C6", borderRadius: 4, fontFamily: "var(--font-roboto-mono, 'Roboto Mono', monospace)", fontSize: 12 }}
                  wrapperStyle={{ zIndex: 50 }}
                  labelStyle={{ color: "#1A2434" }}
                  itemStyle={{ color: "#1375EC" }}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* 중앙 총액 레이블 */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-0.5">
              <p className="text-[9px] font-medium text-muted-foreground">
                {tab === "섹터" ? "주식평가액" : tab === "전체" ? "순자산" : tab === "국장" ? "국내" : "해외"}
              </p>
              <p className="font-data text-base text-foreground">{formatMan(chartTotal)}</p>
            </div>
          </div>

          {/* 범례 목록 */}
          <div className="mt-2 space-y-1.5 border-t border-border pt-3">
            {data.map((item, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="h-2 w-2 flex-shrink-0" style={{ background: item.color }} />
                  <span className="truncate text-xs text-muted-foreground">{item.name}</span>
                </div>
                <div className="flex flex-shrink-0 gap-4">
                  <span className="font-data text-xs text-foreground">{item.value.toFixed(1)}%</span>
                  <span className="w-14 text-right font-data text-xs text-muted-foreground">{formatMan(item.krw)}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
