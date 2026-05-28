"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { PortfolioDashboard } from "@/components/portfolio/dashboard";

export function PortfolioWidget() {
  const { data: snapshot, isLoading } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });
  const { data: history } = useSWR("/api/portfolio/history?limit=8640", () => portfolioApi.history(), { refreshInterval: 60_000 });

  if (isLoading) return <div className="text-xs text-muted-foreground p-2">로딩 중…</div>;
  if (!snapshot) return null;
  return <PortfolioDashboard snapshot={snapshot} history={history ?? []} />;
}
