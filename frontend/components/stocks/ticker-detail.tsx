"use client";

import { useState } from "react";
import useSWR from "swr";

import { TickerCandleChart } from "@/components/charts/ticker-candle-chart";
import { TimingCard } from "@/components/growth/timing-card";
import { ValuationCard } from "@/components/growth/valuation-card";
import { Button } from "@/components/ui/button";
import { growthApi, tickersApi } from "@/lib/api";

interface TickerDetailProps {
  ticker: string;
  universe?: string;
  name?: string | null;
  compact?: boolean;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR");
}

function statusLabel(dataType: string) {
  if (dataType === "ohlcv") return "가격/OHLCV";
  if (dataType === "fundamental") return "펀더멘털";
  if (dataType === "quarterly") return "분기재무";
  if (dataType === "quant") return "퀀트";
  return dataType;
}

export function TickerDetail({ ticker, universe = "sp500", name, compact = false }: TickerDetailProps) {
  const [hydrateMessage, setHydrateMessage] = useState<string | null>(null);
  const [isHydrating, setIsHydrating] = useState(false);
  const [chartRefreshKey, setChartRefreshKey] = useState(0);
  const detailKey = `/api/tickers/${ticker}/overview?universe=${universe}`;
  const valuationKey = `/api/growth/ticker/${ticker}/valuation?universe=${universe}`;
  const timingKey = `/api/growth/ticker/${ticker}/timing`;
  const { data: overview, mutate: mutateOverview } = useSWR(detailKey, () => tickersApi.overview(ticker, universe));
  const { data: valuation, error: valuationError, mutate: mutateValuation } = useSWR(valuationKey, () => growthApi.valuation(ticker, universe));
  const { data: timing, mutate: mutateTiming } = useSWR(timingKey, () => growthApi.timing(ticker));
  const displayName = name || String(overview?.profile?.name ?? "");

  const hydrate = async () => {
    setIsHydrating(true);
    setHydrateMessage(null);
    try {
      const result = await tickersApi.hydrate(ticker, ["ohlcv", "fundamental"]);
      const warnings = result.warnings.length ? ` · ${result.warnings.join(", ")}` : "";
      setHydrateMessage(`${ticker} 가격/OHLCV와 펀더멘털 snapshot 보강을 완료했습니다.${warnings}`);
      setChartRefreshKey((value) => value + 1);
      await Promise.all([mutateOverview(), mutateValuation(), mutateTiming()]);
    } catch (error) {
      const errorText = error instanceof Error ? error.message : "알 수 없는 오류";
      setHydrateMessage(`${ticker} 데이터 보강 중 오류가 발생했습니다: ${errorText}`);
    } finally {
      setIsHydrating(false);
    }
  };

  return (
    <section className="space-y-4">
      {!compact && (
        <header className="rounded-xl border border-border bg-card p-5">
          <p className="font-data text-[10px] tracking-[0.24em] text-primary">TICKER HUB</p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="font-heading text-3xl font-medium tracking-tight">{ticker}</h1>
              <p className="mt-1 text-sm text-muted-foreground">{displayName || "종목을 조회했습니다."}</p>
            </div>
            <Button type="button" onClick={hydrate} disabled={isHydrating}>
              {isHydrating ? "보강 중" : "데이터 보강"}
            </Button>
          </div>
        </header>
      )}

      {compact && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-data text-sm text-primary">{ticker}</p>
            <p className="text-xs text-muted-foreground">{displayName}</p>
          </div>
          <Button type="button" variant="outline" onClick={hydrate} disabled={isHydrating}>
            {isHydrating ? "보강 중" : "데이터 보강"}
          </Button>
        </div>
      )}

      {hydrateMessage && (
        <p className="rounded border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {hydrateMessage}
        </p>
      )}

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="font-data text-[10px] tracking-[0.2em] text-primary">PRICE CHART</p>
            <p className="mt-1 text-xs text-muted-foreground">공통 캐시에 저장된 OHLCV로 그리는 가격 차트입니다.</p>
          </div>
        </div>
        <TickerCandleChart
          ticker={ticker}
          defaultPeriod="3M"
          heightClassName="h-[620px]"
          refreshKey={chartRefreshKey}
        />
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <p className="font-data text-[10px] tracking-[0.2em] text-primary">DATA STATUS</p>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {(overview?.status ?? []).length ? (
            overview!.status.map((status) => (
              <div key={`${status.data_type}-${status.source}`} className="rounded-lg border border-border bg-background/40 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-foreground">{statusLabel(status.data_type)}</span>
                  <span className="font-data text-primary">{status.source}</span>
                </div>
                <p className="mt-2 text-muted-foreground">
                  구간: <span className="font-data text-foreground">{status.min_date ?? "-"}</span> ~{" "}
                  <span className="font-data text-foreground">{status.max_date ?? "-"}</span>
                </p>
                <p className="mt-1 text-muted-foreground">마지막 성공: {formatDate(status.last_success_at)}</p>
                {status.last_error && <p className="mt-1 text-loss">오류: {status.last_error}</p>}
              </div>
            ))
          ) : (
            <p className="rounded-lg border border-border bg-background/40 p-3 text-xs text-muted-foreground">
              아직 공통 데이터 상태가 없습니다. 데이터 보강을 실행하면 보유 구간과 오류 상태가 기록됩니다.
            </p>
          )}
        </div>
      </section>

      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-medium">밸류에이션 검증</p>
            <p className="text-xs text-muted-foreground">공통 펀더멘털 snapshot을 우선 사용합니다.</p>
          </div>
          <ValuationCard data={valuation} error={valuationError} />
        </div>
        <div>
          <div className="mb-2">
            <p className="text-sm font-medium">매수 타이밍 검증</p>
            <p className="text-xs text-muted-foreground">공통 OHLCV 캐시 기반 기술적 검증입니다.</p>
          </div>
          <TimingCard data={timing} />
        </div>
      </div>
    </section>
  );
}
