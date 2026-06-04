"use client";

import type { GrowthScore } from "@/lib/types";

interface Props {
  scores: GrowthScore[];
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}

function factor(value: number | null) {
  if (value === null) return <span className="text-muted-foreground">-</span>;
  const tone = value >= 0.7 ? "text-rise" : value < 0.4 ? "text-fall" : "text-foreground";
  return <span className={`font-data ${tone}`}>{Math.round(value * 100)}</span>;
}

function delta(value: number | null) {
  if (value === null) return <span className="text-muted-foreground">-</span>;
  if (value === 0) return <span className="text-muted-foreground">0</span>;
  return <span className={value > 0 ? "text-rise" : "text-fall"}>{value > 0 ? `+${value}` : value}</span>;
}

export function GrowthRankingTable({ scores, selectedTicker, onSelect }: Props) {
  if (scores.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">성장 점수 데이터가 없습니다.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/60 text-[11px] text-muted-foreground">
            <th className="px-3 py-2 text-left">RANK</th>
            <th className="px-3 py-2 text-left">종목</th>
            <th className="px-3 py-2 text-right">종합</th>
            <th className="px-3 py-2 text-right">1주</th>
            <th className="px-3 py-2 text-right">1달</th>
            <th className="px-3 py-2 text-right">성장</th>
            <th className="px-3 py-2 text-right">수익</th>
            <th className="px-3 py-2 text-right">현금</th>
            <th className="px-3 py-2 text-right">안정</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((score) => (
            <tr
              key={score.ticker}
              onClick={() => onSelect(score.ticker)}
              className={`cursor-pointer border-b border-border transition-colors hover:bg-muted/50 ${
                selectedTicker === score.ticker ? "bg-primary/10" : ""
              }`}
            >
              <td className="px-3 py-2 font-data text-xs text-muted-foreground">{score.rank ?? "-"}</td>
              <td className="px-3 py-2">
                <p className="font-data font-medium text-foreground">{score.ticker}</p>
                <p className="max-w-48 truncate text-[11px] text-muted-foreground">{score.company_name ?? score.sector ?? "-"}</p>
              </td>
              <td className="px-3 py-2 text-right font-data font-medium text-primary">
                {score.growth_composite?.toFixed(1) ?? "-"}
              </td>
              <td className="px-3 py-2 text-right font-data text-xs">{delta(score.delta_1w)}</td>
              <td className="px-3 py-2 text-right font-data text-xs">{delta(score.delta_1m)}</td>
              <td className="px-3 py-2 text-right">{factor(score.pct_growth)}</td>
              <td className="px-3 py-2 text-right">{factor(score.pct_profitability)}</td>
              <td className="px-3 py-2 text-right">{factor(score.pct_cashflow)}</td>
              <td className="px-3 py-2 text-right">{factor(score.pct_stability)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
