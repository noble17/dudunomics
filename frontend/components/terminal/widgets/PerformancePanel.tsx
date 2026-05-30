"use client";
import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { performanceApi } from "@/lib/api";
import { createChart, ColorType, LineStyle } from "lightweight-charts";

type Period = "1m" | "3m" | "6m" | "1y" | "all";
const PERIODS: Period[] = ["1m", "3m", "6m", "1y", "all"];

function PerformanceChart({ data }: { data: { date: string; portfolio: number; kospi: number; sp500: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !data.length) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#0d1929" }, textColor: "#888" },
      grid: { vertLines: { color: "#1e3a5f" }, horzLines: { color: "#1e3a5f" } },
      width: containerRef.current.clientWidth,
      height: 140,
      rightPriceScale: { borderColor: "#1e3a5f" },
      timeScale: { borderColor: "#1e3a5f" },
    });
    const portSeries = chart.addLineSeries({ color: "#4a9eff", lineWidth: 2 });
    const kospiSeries = chart.addLineSeries({ color: "#26c940", lineWidth: 1, lineStyle: LineStyle.Dashed });
    const sp500Series = chart.addLineSeries({ color: "#ff9500", lineWidth: 1, lineStyle: LineStyle.Dashed });

    portSeries.setData(data.map(d => ({ time: d.date as any, value: d.portfolio })));
    kospiSeries.setData(data.map(d => ({ time: d.date as any, value: d.kospi })));
    sp500Series.setData(data.map(d => ({ time: d.date as any, value: d.sp500 })));
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data]);

  return <div ref={containerRef} />;
}

export function PerformancePanel() {
  const [period, setPeriod] = useState<Period>("6m");
  const { data, isLoading } = useSWR(
    `/api/portfolio/performance?period=${period}`,
    () => performanceApi.get(period),
    { refreshInterval: 300_000 }
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] shrink-0">
        <span className="text-[11px] font-data uppercase tracking-widest text-[var(--color-primary)]">PERFORMANCE</span>
        <div className="flex gap-2">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-[11px] font-data uppercase ${
                period === p ? "text-[var(--color-primary)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="px-3 pt-2 shrink-0">
        {data?.chart.length ? (
          <PerformanceChart data={data.chart} />
        ) : (
          <div className="h-[140px] flex items-center justify-center text-[12px] font-data text-[var(--color-text-muted)]">
            {isLoading ? "로딩 중…" : "스냅샷 데이터 없음"}
          </div>
        )}
      </div>
      <div className="px-3 py-2 shrink-0">
        <div className="flex gap-3 text-[12px] font-data flex-wrap">
          <div><span className="text-[var(--color-text-muted)]">Sharpe </span>
            <span className="text-[var(--color-text-primary)]">{data?.sharpe.toFixed(2) ?? "—"}</span></div>
          <div><span className="text-[var(--color-text-muted)]">MDD </span>
            <span className="text-red-400">{data ? `${data.mdd.toFixed(1)}%` : "—"}</span></div>
          <div><span className="text-[var(--color-text-muted)]">YTD </span>
            <span className={data && data.total_return >= 0 ? "text-green-400" : "text-red-400"}>
              {data ? `${data.total_return >= 0 ? "+" : ""}${data.total_return.toFixed(1)}%` : "—"}
            </span></div>
          {data?.benchmark?.kospi && (
            <div><span className="text-[var(--color-text-muted)]">vs KOSPI </span>
              <span className={data.total_return >= data.benchmark.kospi.return_pct ? "text-green-400" : "text-red-400"}>
                {(data.total_return - data.benchmark.kospi.return_pct) >= 0 ? "+" : ""}
                {(data.total_return - data.benchmark.kospi.return_pct).toFixed(1)}%
              </span></div>
          )}
          {data?.benchmark?.sp500 && (
            <div><span className="text-[var(--color-text-muted)]">vs S&P </span>
              <span className={data.total_return >= data.benchmark.sp500.return_pct ? "text-green-400" : "text-red-400"}>
                {(data.total_return - data.benchmark.sp500.return_pct) >= 0 ? "+" : ""}
                {(data.total_return - data.benchmark.sp500.return_pct).toFixed(1)}%
              </span></div>
          )}
        </div>
        <div className="flex gap-3 mt-1.5 text-[11px] font-data">
          <span className="text-[#4a9eff]">■ 포트폴리오</span>
          <span className="text-[#26c940]">■ KOSPI</span>
          <span className="text-[#ff9500]">■ S&P500</span>
        </div>
      </div>
    </div>
  );
}
