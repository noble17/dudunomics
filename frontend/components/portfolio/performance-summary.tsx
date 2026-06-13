"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { createChart, ColorType, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { performanceApi } from "@/lib/api";
import type { PerformanceChartPoint } from "@/lib/types";
import { chartTheme } from "@/lib/design-tokens";

type Period = "1m" | "3m" | "6m" | "1y" | "all";

const PERIODS: Period[] = ["1m", "3m", "6m", "1y", "all"];
const LABEL = "text-[11px] font-medium text-muted-foreground";

function formatPct(value?: number) {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function PerformanceChart({ data }: { data: PerformanceChartPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: chartTheme.bg }, textColor: chartTheme.text },
      grid: { vertLines: { color: chartTheme.grid }, horzLines: { color: chartTheme.grid } },
      width: containerRef.current.clientWidth,
      height: 240,
      rightPriceScale: { borderColor: chartTheme.axisLine },
      timeScale: { borderColor: chartTheme.axisLine },
    });

    const portfolio = chart.addSeries(LineSeries, { color: chartTheme.brand, lineWidth: 2 });
    const kospi = chart.addSeries(LineSeries, { color: chartTheme.palette[4], lineWidth: 1, lineStyle: LineStyle.Dashed });
    const sp500 = chart.addSeries(LineSeries, { color: "#ff9500", lineWidth: 1, lineStyle: LineStyle.Dashed });

    portfolio.setData(data.map((item) => ({ time: item.date as Time, value: item.portfolio })));
    kospi.setData(data.map((item) => ({ time: item.date as Time, value: item.kospi })));
    sp500.setData(data.map((item) => ({ time: item.date as Time, value: item.sp500 })));
    chart.timeScale().fitContent();

    const resize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [data]);

  return <div ref={containerRef} className="h-60 w-full" />;
}

function Metric({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const color = positive == null ? "text-foreground" : positive ? "text-gain" : "text-loss";
  return (
    <div className="border border-border bg-background px-4 py-3">
      <div className={LABEL}>{label}</div>
      <div className={`mt-2 font-data text-lg ${color}`}>{value}</div>
    </div>
  );
}

export function PortfolioPerformanceSummary() {
  const [period, setPeriod] = useState<Period>("6m");
  const { data, isLoading } = useSWR(
    `/api/portfolio/performance?period=${period}`,
    () => performanceApi.get(period),
    { refreshInterval: 300_000 },
  );

  const kospi = data?.benchmark?.kospi?.return_pct;
  const sp500 = data?.benchmark?.sp500?.return_pct;

  return (
    <section className="border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div>
          <p className={LABEL}>성과 분석</p>
          <p className="mt-1 text-xs text-muted-foreground">
            5분마다 저장되는 포트폴리오 스냅샷으로 기간 수익률, MDD, 벤치마크를 비교합니다.
          </p>
        </div>
        <div className="flex gap-1">
          {PERIODS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setPeriod(item)}
              className={`border px-3 py-1.5 font-data text-xs uppercase transition-colors ${
                period === item
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:border-primary hover:text-foreground"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          {data?.chart.length ? (
            <PerformanceChart data={data.chart} />
          ) : (
            <div className="flex h-60 items-center justify-center text-sm text-muted-foreground">
              {isLoading ? "성과 데이터를 불러오는 중입니다." : "선택한 기간에 표시할 스냅샷이 아직 부족합니다."}
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-4 font-data text-xs">
            <span className="text-primary">■ 포트폴리오</span>
            <span className="text-[#a78bfa]">■ KOSPI</span>
            <span className="text-[#ff9500]">■ S&P500</span>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          <Metric label="총 수익률" value={formatPct(data?.total_return)} positive={(data?.total_return ?? 0) >= 0} />
          <Metric label="연환산 수익률" value={formatPct(data?.annualized_return)} positive={(data?.annualized_return ?? 0) >= 0} />
          <Metric label="Sharpe" value={data ? data.sharpe.toFixed(2) : "-"} />
          <Metric label="MDD" value={data ? formatPct(data.mdd) : "-"} positive={false} />
          <Metric label="vs KOSPI" value={kospi == null || !data ? "-" : formatPct(data.total_return - kospi)} positive={kospi != null && data != null && data.total_return >= kospi} />
          <Metric label="vs S&P500" value={sp500 == null || !data ? "-" : formatPct(data.total_return - sp500)} positive={sp500 != null && data != null && data.total_return >= sp500} />
        </div>
      </div>
    </section>
  );
}
