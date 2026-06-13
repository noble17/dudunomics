import type { ReactNode } from "react";

import type { GrowthValuation } from "@/lib/types";

function metric(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toFixed(2)}${suffix}`;
}

function price(value: number | null) {
  return value === null
    ? "-"
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function unavailable(label = "미제공") {
  return <span className="text-xs text-muted-foreground">{label}</span>;
}

function priceRange(low: number | null, high: number | null) {
  if (low !== null && high !== null) return `${price(low)} - ${price(high)}`;
  return low !== null || high !== null ? price(low ?? high) : null;
}

function sourceName(source: string) {
  if (source === "BATCH") return "Growth Batch";
  if (source === "FINVIZ") return "Finviz";
  if (source === "STOCKANALYSIS") return "StockAnalysis";
  if (source === "finviz_stockanalysis") return "Finviz + StockAnalysis";
  return source;
}

function SourceBadge({ source }: { source: GrowthValuation["consensus_source"] }) {
  if (!source) return null;

  return (
    <span className="border border-primary/40 bg-primary/10 px-1.5 py-0.5 font-data text-[10px] text-primary">
      {sourceName(source)}
    </span>
  );
}

function Attempts({ data }: { data: GrowthValuation }) {
  if (!data.fallback_used && data.consensus_attempts.length <= 1) return null;

  return (
    <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
      <p className="font-medium text-foreground">
        {data.fallback_used ? "대체 조회 경로" : "조회 경로"}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {data.consensus_attempts.map((attempt) => (
          <span key={`${attempt.source}-${attempt.status}`} className="rounded border border-border px-2 py-1">
            {sourceName(attempt.source)} · {attempt.status}
          </span>
        ))}
      </div>
    </div>
  );
}

function ConsensusMessage({ data, fallback }: { data: GrowthValuation; fallback: string }) {
  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      <SourceBadge source={data.consensus_source} />
      <p>{data.consensus_message || fallback}</p>
      <Attempts data={data} />
    </div>
  );
}

function ConsensusContent({ data, error }: { data?: GrowthValuation; error?: unknown }) {
  if (error) {
    return <p className="text-xs text-muted-foreground">목표주가 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>;
  }

  if (!data) {
    return <p className="text-xs text-muted-foreground">불러오는 중</p>;
  }

  if (data.consensus_status === "ok") {
    const upsideTone = data.upside_pct == null
      ? "text-foreground"
      : data.upside_pct >= 0
        ? "text-gain"
        : "text-loss";
    const upsideLabel = data.upside_pct == null ? "-" : `${data.upside_pct.toFixed(1)}%`;
    const rows: Array<[string, ReactNode]> = [
      ["중앙값", data.target_median == null ? unavailable() : price(data.target_median)],
      ["범위", priceRange(data.target_low, data.target_high) ?? unavailable()],
      ["참여기관", data.analyst_count == null ? unavailable() : `${data.analyst_count}곳`],
      ["기준일", data.consensus_as_of ?? unavailable()],
    ];
    const partialSource = data.consensus_source === "STOCKANALYSIS" || data.consensus_source === "FINVIZ";

    return (
      <div>
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
          <div className="flex items-start justify-between gap-3">
            <p className="text-xs font-medium text-primary">목표주가 요약</p>
            <SourceBadge source={data.consensus_source} />
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div>
              <p className="text-[10px] text-muted-foreground">평균 목표주가</p>
              <p className="mt-1 font-data text-lg text-foreground">{price(data.target_mean)}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground">현재가</p>
              <p className="mt-1 font-data text-lg text-foreground">{price(data.current_price)}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-muted-foreground">상승 여력</p>
              <p className={`mt-1 font-data text-lg ${upsideTone}`}>{upsideLabel}</p>
            </div>
          </div>
        </div>
        {partialSource && (data.target_median == null || data.target_low == null || data.target_high == null || data.analyst_count == null) && (
          <p className="mt-3 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            {sourceName(data.consensus_source!)} fallback은 평균 목표주가만 제공하는 경우가 있어 중앙값, 범위, 참여기관, 기준일이 비어 있을 수 있습니다.
          </p>
        )}
        <div className="mt-4 space-y-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between border-b border-border pb-2 text-sm last:border-0">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-data text-foreground">{value}</span>
            </div>
          ))}
        </div>
        {data.consensus_message && <p className="mt-3 text-xs text-muted-foreground">{data.consensus_message}</p>}
        <Attempts data={data} />
      </div>
    );
  }

  if (data.consensus_status === "no_data") {
    return <ConsensusMessage data={data} fallback="최근 6개월 내 목표주가 데이터가 없습니다." />;
  }

  if (data.consensus_status === "missing") {
    return <ConsensusMessage data={data} fallback="목표주가 데이터가 아직 적재되지 않았습니다." />;
  }

  if (data.consensus_status === "rate_limited") {
    return (
      <div className="space-y-2">
        <ConsensusMessage
          data={data}
          fallback="API 한도를 초과했습니다. 다음 한도 초기화 이후 다시 조회할 수 있습니다."
        />
        {data.retry_after && <p className="font-data text-xs text-muted-foreground">재조회 가능: {data.retry_after}</p>}
      </div>
    );
  }

  if (data.consensus_status === "temporary_error") {
    return <ConsensusMessage data={data} fallback="일시적인 오류가 발생했습니다. 잠시 후 다시 조회해 주세요." />;
  }

  if (data.consensus_status === "subscription_limited") {
    return <ConsensusMessage data={data} fallback="현재 API 요금제에서 이 종목의 목표주가 조회를 지원하지 않습니다." />;
  }

  if (data.consensus_status === "missing_key") {
    return <ConsensusMessage data={data} fallback="목표주가 컨센서스를 조회하려면 API 키 설정이 필요합니다." />;
  }

  return <ConsensusMessage data={data} fallback="목표주가 상태를 확인할 수 없습니다." />;
}

export function ValuationCard({ data, error }: { data?: GrowthValuation; error?: unknown }) {
  const rows = [
    ["PEG", metric(data?.peg ?? null)],
    ["Forward PER", metric(data?.forward_pe ?? null, "x")],
    ["PSR", metric(data?.psr ?? null, "x")],
    ["Forward EPS", metric(data?.forward_eps ?? null)],
    ["컨센서스 매출 CAGR", data?.forward_revenue_growth == null ? "-" : `${(data.forward_revenue_growth * 100).toFixed(1)}%`],
    ["컨센서스 EPS CAGR", data?.forward_eps_growth == null ? "-" : `${(data.forward_eps_growth * 100).toFixed(1)}%`],
  ];

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-[11px] font-medium tracking-[0.18em] text-primary">VALUATION CHECK</h3>
      <ValuationStatus data={data} />
      {data?.score_status === "missing" && (
        <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-3">
          <p className="text-xs font-medium text-primary">성장주 배치 데이터 없음</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {data.score_message ?? "이 종목은 아직 성장주 배치 점수에 포함되지 않았습니다."}
          </p>
        </div>
      )}
      <div className="mt-4 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between border-b border-border pb-2 text-sm last:border-0">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-data text-foreground">{value}</span>
          </div>
        ))}
      </div>
      {data?.missing_reasons?.length ? (
        <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs font-medium text-foreground">미제공 항목</p>
          <div className="mt-2 space-y-1">
            {data.missing_reasons.map((reason) => (
              <p key={reason} className="text-xs text-muted-foreground">{reason}</p>
            ))}
          </div>
        </div>
      ) : null}
      <div className="my-4 border-t border-border" />
      <div>
        <h3 className="mb-4 text-[11px] font-medium tracking-[0.18em] text-primary">PRICE TARGET CONSENSUS</h3>
        <ConsensusContent data={data} error={error} />
      </div>
    </section>
  );
}

function ValuationStatus({ data }: { data?: GrowthValuation }) {
  if (!data) {
    return (
      <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        펀더멘털 snapshot 상태를 불러오는 중입니다.
      </div>
    );
  }

  const hasValuation = Boolean(data.valuation_source);
  return (
    <div className={`mt-3 rounded-lg border p-3 text-xs ${
      hasValuation ? "border-border bg-muted/30" : "border-amber-500/30 bg-amber-500/10"
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-foreground">펀더멘털 snapshot</span>
        <span className={`border px-2 py-0.5 font-data text-[10px] ${
          hasValuation ? "border-primary/40 bg-primary/10 text-primary" : "border-amber-500/30 text-amber-700 dark:text-amber-200"
        }`}>
          {hasValuation ? sourceName(data.valuation_source!) : "보강 필요"}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
        <span>기준일: <span className="font-data text-foreground">{data.valuation_as_of ?? "-"}</span></span>
        <span>상태: {data.valuation_stale ? "오래됨" : hasValuation ? "사용 가능" : "없음"}</span>
      </div>
    </div>
  );
}
