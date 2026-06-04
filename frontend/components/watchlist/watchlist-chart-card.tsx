"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { candlesApi } from "@/lib/api";
import type { CandleItem, WatchlistItem } from "@/lib/types";

const PERIODS = ["1M", "3M", "6M", "YTD", "1Y"] as const;
type Period = typeof PERIODS[number];

const PERIOD_TO_API: Record<Period, string> = {
  "1M": "1M",
  "3M": "3M",
  "6M": "6M",
  YTD: "YTD",
  "1Y": "1Y",
};

interface Props {
  ticker: string;
  row: WatchlistItem | null;
  refreshKey?: number;
}

function number(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function compact(value: number | null | undefined) {
  if (value == null) return "-";
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function RangeBar({ label, low, high, price }: { label: string; low?: number | null; high?: number | null; price?: number | null }) {
  const position = price != null && low != null && high != null && high > low
    ? Math.min(100, Math.max(0, ((price - low) / (high - low)) * 100))
    : null;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-data">{number(low)} - {number(high)}</span>
      </div>
      <div className="relative h-2 rounded-full bg-muted">
        {position != null && (
          <span
            className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-card"
            style={{ left: `${position}%` }}
          />
        )}
      </div>
    </div>
  );
}

function changePct(candles: CandleItem[]) {
  if (candles.length < 2) return null;
  const first = candles[0].close;
  const last = candles[candles.length - 1].close;
  return first > 0 ? ((last - first) / first) * 100 : null;
}

export function WatchlistChartCard({ ticker, row, refreshKey = 0 }: Props) {
  const [period, setPeriod] = useState<Period>("3M");
  const { data, error, isLoading } = useSWR(
    `/api/candles?ticker=${ticker}&period=${PERIOD_TO_API[period]}&refresh=${refreshKey}`,
    () => candlesApi.get(ticker, PERIOD_TO_API[period]),
  );
  const candles = useMemo(() => data?.candles ?? [], [data?.candles]);
  const pct = changePct(candles);
  const latest = candles.at(-1);
  const previous = candles.at(-2);
  const gain = pct != null && pct >= 0;

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <p className="font-data text-[10px] tracking-[0.2em] text-primary">PRICE CHART</p>
          <p className="mt-1 text-sm text-muted-foreground">Daily OHLCV 기반 기간 차트입니다.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setPeriod(value)}
              className={`rounded-lg border px-3 py-1.5 font-data text-xs ${
                period === value ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:border-primary/50"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 p-4 xl:grid-cols-[1fr_260px]">
        <div className="min-h-[280px]">
          {isLoading ? (
            <div className="flex h-[280px] items-center justify-center text-xs text-muted-foreground">차트를 불러오는 중입니다.</div>
          ) : error ? (
            <div className="flex h-[280px] items-center justify-center rounded-lg border border-loss/30 bg-loss/5 px-4 text-center text-xs text-loss">
              차트 조회 중 오류가 발생했습니다. 데이터 보강 후 다시 시도해 주세요.
            </div>
          ) : candles.length ? (
            <>
              <div className="mb-3 flex items-center gap-3">
                <span className="font-data text-lg text-foreground">{number(latest?.close)}</span>
                {pct != null && (
                  <span className={`rounded border px-2 py-1 font-data text-xs ${gain ? "border-gain/40 text-gain" : "border-loss/40 text-loss"}`}>
                    {gain ? "+" : ""}{pct.toFixed(2)}%
                  </span>
                )}
              </div>
              <ResponsiveContainer width="100%" height={210}>
                <LineChart data={candles} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="rgba(214,224,239,0.12)" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#8b8b95" }} tickMargin={8} minTickGap={28} />
                  <YAxis orientation="right" tick={{ fontSize: 10, fill: "#8b8b95" }} width={48} domain={["dataMin", "dataMax"]} />
                  <Tooltip
                    formatter={(value: unknown, name: unknown) => [
                      typeof value === "number" ? number(value) : String(value),
                      String(name ?? ""),
                    ]}
                    contentStyle={{ background: "#101116", border: "1px solid rgba(214,224,239,0.18)", borderRadius: 10, fontSize: 12 }}
                    labelStyle={{ color: "#d6e0ef" }}
                  />
                  <Line type="monotone" dataKey="close" name="Close" stroke="#ff7a1a" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <ResponsiveContainer width="100%" height={58}>
                <BarChart data={candles} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <Bar dataKey="volume" fill="rgba(139,139,149,0.45)" />
                </BarChart>
              </ResponsiveContainer>
            </>
          ) : (
            <div className="flex h-[280px] items-center justify-center rounded-lg border border-border bg-background/40 text-xs text-muted-foreground">
              차트 데이터가 없습니다. 데이터 보강을 먼저 실행해 주세요.
            </div>
          )}
        </div>
        <aside className="space-y-4 rounded-lg border border-border bg-background/35 p-4">
          <RangeBar label="Day Range" low={row?.day_low} high={row?.day_high} price={row?.price} />
          <RangeBar label="52W Range" low={row?.range_52w_low} high={row?.range_52w_high} price={row?.price} />
          <div className="space-y-2 border-t border-border pt-3 text-sm">
            <p className="flex justify-between gap-3 text-muted-foreground"><span>Volume</span><span className="font-data text-foreground">{compact(row?.volume ?? latest?.volume)}</span></p>
            <p className="flex justify-between gap-3 text-muted-foreground"><span>Avg Vol</span><span className="font-data text-foreground">{compact(row?.avg_volume20)}</span></p>
            <p className="flex justify-between gap-3 text-muted-foreground"><span>Prev Close</span><span className="font-data text-foreground">{number(previous?.close)}</span></p>
            <p className="flex justify-between gap-3 text-muted-foreground"><span>Period</span><span className="font-data text-foreground">{period}</span></p>
            <p className="flex justify-between gap-3 text-muted-foreground"><span>Data From</span><span className="font-data text-foreground">{candles[0]?.time ?? "-"}</span></p>
            {!candles.length && !isLoading && !error && (
              <p className="rounded border border-border bg-muted/30 px-2 py-1 text-xs text-muted-foreground">
                캐시에 {period} 구간 데이터가 없습니다.
              </p>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}
