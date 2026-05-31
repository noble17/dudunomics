"use client";

import { useRouter } from "next/navigation";
import type { QuantScore, FactorWeights } from "@/lib/types";

interface Props {
  scores: QuantScore[];
  weights: FactorWeights;
  hardFilters: { ma200: boolean };
  sectorFilter: string;
  industryFilter: string;
  topN?: number;
  universe?: string;
  isBatchRunning?: boolean;
}

function normalizeWeights(w: FactorWeights): FactorWeights {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (total === 0) return { momentum: 0.2, valuation: 0.2, eps_momentum: 0.2, quality: 0.2, technical: 0.2 };
  return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v / total])) as unknown as FactorWeights;
}

function compositeScore(s: QuantScore, w: FactorWeights): number {
  const pairs: [number | null, number][] = [
    [s.pct_momentum,     w.momentum],
    [s.pct_valuation,    w.valuation],
    [s.pct_eps_momentum, w.eps_momentum],
    [s.pct_quality,      w.quality],
    [s.pct_technical,    w.technical],
  ];
  let sum = 0, totalW = 0;
  for (const [val, wt] of pairs) {
    if (val !== null && wt > 0) { sum += val * wt; totalW += wt; }
  }
  return totalW > 0 ? sum / totalW : 0;
}

function pctCell(val: number | null) {
  if (val === null) return <td className="px-2 py-1.5 text-right text-muted-foreground text-xs">—</td>;
  const color = val >= 0.7 ? "text-green-600" : val <= 0.3 ? "text-red-500" : "text-amber-500";
  return <td className={`px-2 py-1.5 text-right text-xs font-medium ${color}`}>{val.toFixed(2)}</td>;
}

export function RankingTable({ scores, weights, hardFilters, sectorFilter, industryFilter, topN = 50, universe = "sp500", isBatchRunning = false }: Props) {
  const router = useRouter();
  const norm = normalizeWeights(weights);

  const filtered = scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (sectorFilter && s.sector !== sectorFilter) return false;
    if (industryFilter && s.industry !== industryFilter) return false;
    return true;
  });

  const ranked = filtered
    .map((s) => ({ ...s, composite: compositeScore(s, norm) }))
    .sort((a, b) => b.composite - a.composite)
    .slice(0, topN);

  if (ranked.length === 0) {
    if (isBatchRunning) {
      return (
        <div className="py-12 text-center space-y-2">
          <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground text-sm">데이터 수집 중... 완료 후 자동으로 표시됩니다.</p>
        </div>
      );
    }
    return <p className="text-muted-foreground text-sm py-8 text-center">데이터 없음. 오른쪽 상단 &quot;데이터 갱신&quot; 버튼으로 배치를 실행하세요.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-2 text-left text-xs text-muted-foreground w-8">#</th>
            <th className="px-2 py-2 text-left text-xs text-muted-foreground">티커</th>
            <th className="px-2 py-2 text-left text-xs text-muted-foreground">종목명</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">종합</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">모멘텀</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">밸류</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">EPS</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">퀄리티</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">기술적</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((s, i) => (
            <tr
              key={s.ticker}
              className="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/screener/${s.ticker}?universe=${universe}`)}
            >
              <td className="px-2 py-1.5 text-xs text-muted-foreground">{i + 1}</td>
              <td className="px-2 py-1.5 font-bold text-blue-700">{s.ticker}</td>
              <td className="px-2 py-1.5 text-xs text-muted-foreground max-w-[140px] truncate">{s.company_name ?? "—"}</td>
              <td className="px-2 py-1.5 text-right">
                <span className="bg-blue-100 text-blue-800 rounded px-1.5 py-0.5 text-xs font-bold">
                  {s.composite.toFixed(2)}
                </span>
              </td>
              {pctCell(s.pct_momentum)}
              {pctCell(s.pct_valuation)}
              {pctCell(s.pct_eps_momentum)}
              {pctCell(s.pct_quality)}
              {pctCell(s.pct_technical)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
