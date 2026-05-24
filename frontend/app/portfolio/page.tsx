// frontend/app/portfolio/page.tsx
"use client";

import useSWR from "swr";
import { useState } from "react";
import { portfolioApi } from "@/lib/api";
import { KpiCards } from "@/components/portfolio/kpi-cards";
import { WeightPie } from "@/components/portfolio/weight-pie";
import { EquityCurve } from "@/components/portfolio/equity-curve";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PortfolioPage() {
  const [currency, setCurrency] = useState<"KRW" | "USD">("KRW");
  const [weightMode, setWeightMode] = useState<"equity" | "total">("equity");

  const { data: snapshot, error: snapErr, isLoading: snapLoading } =
    useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  const { data: history } =
    useSWR("/api/portfolio/history", portfolioApi.history, { refreshInterval: 60_000 });

  if (snapLoading) return <div className="py-12 text-center text-muted-foreground">로딩 중…</div>;
  if (snapErr) return <div className="py-12 text-center text-destructive">데이터 로드 실패. API 서버를 확인하세요.</div>;
  if (!snapshot) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">포트폴리오</h1>
        <div className="flex gap-3">
          <Tabs value={currency} onValueChange={(v) => setCurrency(v as "KRW" | "USD")}>
            <TabsList>
              <TabsTrigger value="KRW">KRW</TabsTrigger>
              <TabsTrigger value="USD">USD</TabsTrigger>
            </TabsList>
          </Tabs>
          <Tabs value={weightMode} onValueChange={(v) => setWeightMode(v as "equity" | "total")}>
            <TabsList>
              <TabsTrigger value="equity">주식만</TabsTrigger>
              <TabsTrigger value="total">주식+현금</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      <KpiCards snapshot={snapshot} currency={currency} weightMode={weightMode} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-base">비중</CardTitle></CardHeader>
          <CardContent className="pb-4">
            <WeightPie rows={snapshot.rows} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="text-base">평가액 추이</CardTitle></CardHeader>
          <CardContent className="pb-4">
            <EquityCurve history={history ?? []} currency={currency} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">보유종목</CardTitle></CardHeader>
        <CardContent className="p-0">
          <HoldingsTable rows={snapshot.rows} currency={currency} usdkrw={snapshot.usdkrw} />
        </CardContent>
      </Card>

      <p className="text-right text-xs text-muted-foreground">
        마지막 갱신: {new Date(snapshot.updated_at).toLocaleString("ko-KR")}
      </p>
    </div>
  );
}
