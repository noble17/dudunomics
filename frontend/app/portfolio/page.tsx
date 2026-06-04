// frontend/app/portfolio/page.tsx
"use client";

import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { PortfolioDashboard } from "@/components/portfolio/dashboard";
import { PerformanceTable } from "@/components/performance/performance-table";

export default function PortfolioPage() {
  const { data: snapshot, error, isLoading } =
    useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  const { data: history } =
    useSWR("/api/portfolio/history?limit=8640", () => portfolioApi.history(), { refreshInterval: 60_000 });
  const { data: analytics = [], isLoading: analyticsLoading } =
    useSWR("/api/portfolio/analytics", portfolioApi.analytics, { refreshInterval: 60_000 });

  if (isLoading) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        로딩 중…
      </div>
    );
  }
  if (error) {
    return (
      <div className="py-12 text-center text-sm text-error">
        데이터 로드 실패 — API 서버를 확인하세요.
      </div>
    );
  }
  if (!snapshot) return null;

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-2xl font-bold tracking-tight">포트폴리오</h1>
      <PortfolioDashboard snapshot={snapshot} history={history ?? []} />
      <section className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-5 py-3">
          <p className="text-sm font-medium">Performance View</p>
          <p className="mt-1 text-xs text-muted-foreground">
            보유 종목의 기간 수익률과 20D/50D/200D MA 대비율을 함께 봅니다.
          </p>
        </div>
        {analyticsLoading ? (
          <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
            성과 지표를 불러오는 중입니다.
          </div>
        ) : analytics.length > 0 ? (
          <PerformanceTable rows={analytics} mode="portfolio" />
        ) : (
          <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
            표시할 보유 종목이 없습니다.
          </div>
        )}
      </section>
    </div>
  );
}
