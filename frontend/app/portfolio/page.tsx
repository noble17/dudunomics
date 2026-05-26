// frontend/app/portfolio/page.tsx
"use client";

import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { PortfolioDashboard } from "@/components/portfolio/dashboard";

export default function PortfolioPage() {
  const { data: snapshot, error, isLoading } =
    useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  const { data: history } =
    useSWR("/api/portfolio/history?limit=8640", () => portfolioApi.history(), { refreshInterval: 60_000 });

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
    </div>
  );
}
