// frontend/components/screener/metric-grid.tsx
import type { QuantScore } from "@/lib/types";

// RSI 컬러링: 40–70 = 초록(건전 추세), 30–40 = 노랑(경계), ≥70 또는 ≤30 = 빨강(과열/과매도)
function rsiColor(rsi: number | null): string {
  if (rsi === null) return "text-muted-foreground";
  if (rsi >= 40 && rsi < 70) return "text-green-600";
  if (rsi >= 30 && rsi < 40) return "text-amber-500";
  return "text-red-500";
}

function metricColor(val: number | null, goodBelow: boolean, goodThreshold: number, warnThreshold: number): string {
  if (val === null) return "text-muted-foreground";
  if (goodBelow) {
    if (val < goodThreshold) return "text-green-600";
    if (val > warnThreshold) return "text-red-500";
    return "text-amber-500";
  } else {
    if (val > goodThreshold) return "text-green-600";
    if (val < warnThreshold) return "text-red-500";
    return "text-amber-500";
  }
}

function fmt(val: number | null, decimals = 1, suffix = "x"): string {
  if (val === null) return "—";
  return `${val.toFixed(decimals)}${suffix}`;
}

function fmtPct(val: number | null): string {
  if (val === null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

interface Metric {
  label: string;
  value: string;
  sub: string;
  colorClass: string;
}

export function MetricGrid({ score }: { score: QuantScore }) {
  const metrics: Metric[] = [
    {
      label: "Trailing PER",
      value: fmt(score.raw_trailing_pe),
      sub: "S&P500 avg ~21x",
      colorClass: metricColor(score.raw_trailing_pe, true, 21, 40),
    },
    {
      label: "Forward PER",
      value: fmt(score.raw_fwd_pe),
      sub: "S&P500 avg ~18x",
      colorClass: metricColor(score.raw_fwd_pe, true, 18, 35),
    },
    {
      label: "PBR",
      value: fmt(score.raw_pbr),
      sub: "S&P500 avg ~4x",
      colorClass: metricColor(score.raw_pbr, true, 4, 10),
    },
    {
      label: "PSR",
      value: fmt(score.raw_psr),
      sub: "S&P500 avg ~2.8x",
      colorClass: metricColor(score.raw_psr, true, 3, 10),
    },
    {
      label: "EPS (TTM)",
      value: score.raw_eps_ttm !== null ? `$${score.raw_eps_ttm.toFixed(2)}` : "—",
      sub: "Trailing 12M",
      colorClass: score.raw_eps_ttm !== null && score.raw_eps_ttm > 0 ? "text-green-600" : "text-red-500",
    },
    {
      label: "Fwd EPS",
      value: score.raw_fwd_eps !== null ? `$${score.raw_fwd_eps.toFixed(2)}` : "—",
      sub: score.raw_eps_ttm && score.raw_fwd_eps
        ? `vs TTM ${score.raw_fwd_eps > score.raw_eps_ttm ? "+" : ""}${(((score.raw_fwd_eps - score.raw_eps_ttm) / Math.abs(score.raw_eps_ttm)) * 100).toFixed(0)}%`
        : "Forward 12M",
      colorClass: score.raw_fwd_eps !== null && score.raw_fwd_eps > (score.raw_eps_ttm ?? 0) ? "text-green-600" : "text-amber-500",
    },
    {
      label: "ROE",
      value: fmtPct(score.raw_roe),
      sub: "Return on Equity",
      colorClass: metricColor(score.raw_roe, false, 0.15, 0.05),
    },
    {
      label: "D/E Ratio",
      value: score.raw_debt_ratio !== null ? score.raw_debt_ratio.toFixed(2) : "—",
      sub: "Debt / Equity",
      colorClass: metricColor(score.raw_debt_ratio, true, 0.5, 2.0),
    },
    {
      label: "RSI (14)",
      value: score.raw_rsi !== null ? score.raw_rsi.toFixed(1) : "—",
      sub: score.raw_rsi !== null
        ? score.raw_rsi >= 70 ? "과열 구간" : score.raw_rsi <= 30 ? "과매도" : score.raw_rsi >= 40 ? "건전 추세" : "약세 경계"
        : "",
      colorClass: rsiColor(score.raw_rsi),
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-2">
      {metrics.map(({ label, value, sub, colorClass }) => (
        <div key={label} className="rounded-lg bg-muted/40 px-3 py-2 border border-border">
          <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
          <p className={`text-base font-bold ${colorClass}`}>{value}</p>
          <p className="text-xs text-muted-foreground">{sub}</p>
        </div>
      ))}
    </div>
  );
}
