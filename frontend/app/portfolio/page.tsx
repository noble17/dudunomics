// frontend/app/portfolio/page.tsx
"use client";

import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { PortfolioDashboard } from "@/components/portfolio/dashboard";
import { MarketStrip } from "@/components/market/market-strip";

export default function PortfolioPage() {
  const { data: snapshot, error, isLoading } =
    useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  const { data: history } =
    useSWR("/api/portfolio/history?bucket=10m&limit=400", () => portfolioApi.history("10m", 400), { refreshInterval: 60_000 });
  const { data: analytics = [] } =
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
      <MarketStrip />
      <PortfolioDashboard snapshot={snapshot} history={history ?? []} analytics={analytics} />
    </div>
  );
}
