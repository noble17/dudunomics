// frontend/app/screener/page.tsx
"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import type { FactorWeights } from "@/lib/types";
import { FactorSidebar } from "@/components/screener/factor-sidebar";
import { RankingTable } from "@/components/screener/ranking-table";

const DEFAULT_WEIGHTS: FactorWeights = {
  momentum: 25,
  valuation: 20,
  eps_momentum: 20,
  quality: 20,
  technical: 15,
};

export default function ScreenerPage() {
  const [universe, setUniverse] = useState("sp500");
  const [weights, setWeights]   = useState<FactorWeights>(DEFAULT_WEIGHTS);
  const [hardFilters, setHardFilters] = useState({ ma200: true, cfo: true });
  const [refreshing, setRefreshing]   = useState(false);

  const { data: scores = [], isLoading, error } = useSWR(
    `/api/screener/scores?universe=${universe}`,
    () => screenerApi.scores(universe)
  );

  const filteredCount = useMemo(() => scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (hardFilters.cfo  && s.cfo_positive === false) return false;
    return true;
  }).length, [scores, hardFilters]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await screenerApi.refresh(universe); }
    finally { setRefreshing(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-bold tracking-tight">종목분석 — 퀀트 스크리닝</h1>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50"
        >
          {refreshing ? "배치 실행 중..." : "데이터 갱신"}
        </button>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">로딩 중...</p>}
      {error && (
        <p className="text-sm text-amber-600">
          데이터 없음 — &quot;데이터 갱신&quot; 버튼으로 배치 실행 후 새로고침 하세요.
        </p>
      )}

      <div className="flex gap-6 items-start">
        <FactorSidebar
          universe={universe}
          onUniverseChange={setUniverse}
          weights={weights}
          onWeightsChange={setWeights}
          hardFilters={hardFilters}
          onHardFiltersChange={setHardFilters}
          totalCount={scores.length}
          filteredCount={filteredCount}
        />

        <div className="flex-1 min-w-0">
          {scores.length > 0 && (
            <p className="text-xs text-muted-foreground mb-2">
              {scores[0]?.as_of} 기준 · 상위 50개 표시
            </p>
          )}
          <RankingTable
            scores={scores}
            weights={weights}
            hardFilters={hardFilters}
            topN={50}
          />
        </div>
      </div>
    </div>
  );
}
