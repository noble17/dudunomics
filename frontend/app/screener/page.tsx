// frontend/app/screener/page.tsx
"use client";

import { useState, useMemo, useEffect, useRef } from "react";
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

const FACTOR_HELP = [
  { label: "가격 모멘텀", desc: "최근 12개월 수익률 (직전 1개월 제외). 상승 추세 주식 선호." },
  { label: "밸류에이션",  desc: "Forward PER + PBR 조합. 낮을수록 저평가 → 높은 점수." },
  { label: "EPS 모멘텀",  desc: "Forward EPS ÷ Trailing EPS. 이익 성장 가속도 측정." },
  { label: "퀄리티",      desc: "ROE와 부채비율 조합. 수익성 높고 레버리지 낮을수록 유리." },
  { label: "기술적 지표", desc: "RSI(14) 백분위 × 60% + 200일 MA 상회 여부 × 40%." },
];

export default function ScreenerPage() {
  const DOMESTIC = ["kospi200", "kosdaq150"];
  const handleUniverseChange = (u: string) => {
    setUniverse(u);
    if (DOMESTIC.includes(u)) setHardFilters({ ma200: false });
    else setHardFilters({ ma200: true });
  };
  const [universe, setUniverse] = useState("sp500");
  const [weights, setWeights]   = useState<FactorWeights>(DEFAULT_WEIGHTS);
  const [helpOpen, setHelpOpen] = useState(false);
  const [hardFilters, setHardFilters] = useState({ ma200: true });
  const [sectorFilter, setSectorFilter] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");
  const [refreshing, setRefreshing]   = useState(false);
  const [refreshMsg, setRefreshMsg]   = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<{
    status: string; step: string; done: number; total: number;
  } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: scores = [], isLoading, error, mutate } = useSWR(
    `/api/screener/scores?universe=${universe}`,
    () => screenerApi.scores(universe)
  );

  // 배치 진행 상태 폴링
  const startPolling = (u: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const st = await screenerApi.status(u);
        setBatchStatus(st);
        if (st.status === "done") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setRefreshing(false);
          setRefreshMsg(null);
          mutate();
        } else if (st.status === "error") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setRefreshing(false);
          setRefreshMsg(`오류: ${st.step}`);
          setBatchStatus(null);
        }
      } catch { /* ignore */ }
    }, 3000);
  };

  // 페이지 복귀 시 배치가 이미 실행 중이면 폴링 재개
  useEffect(() => {
    screenerApi.status(universe).then((st) => {
      if (st.status === "running") {
        setRefreshing(true);
        setBatchStatus(st);
        startPolling(universe);
      }
    }).catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [universe]);

  const sectors = useMemo(
    () => [...new Set(scores.map((s) => s.sector).filter((s): s is string => !!s))].sort(),
    [scores]
  );

  const industries = useMemo(
    () =>
      sectorFilter
        ? [...new Set(
            scores
              .filter((s) => s.sector === sectorFilter)
              .map((s) => s.industry)
              .filter((i): i is string => !!i)
          )].sort()
        : [],
    [scores, sectorFilter]
  );

  const handleSectorChange = (s: string) => {
    setSectorFilter(s);
    setIndustryFilter("");
  };

  const filteredCount = useMemo(() => scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (sectorFilter && s.sector !== sectorFilter) return false;
    if (industryFilter && s.industry !== industryFilter) return false;
    return true;
  }).length, [scores, hardFilters, sectorFilter, industryFilter]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMsg(null);
    setBatchStatus(null);
    try {
      await screenerApi.refresh(universe);
      startPolling(universe);
    } catch (e) {
      setRefreshMsg(`오류: ${e instanceof Error ? e.message : String(e)}`);
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-2xl font-bold tracking-tight">종목분석 — 퀀트 스크리닝</h1>
          <button
            onClick={() => setHelpOpen((v) => !v)}
            className="rounded-full w-5 h-5 text-xs border border-border text-muted-foreground hover:bg-muted flex items-center justify-center"
            title="사용법"
          >
            ?
          </button>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50"
        >
          {refreshing ? "배치 실행 중..." : "데이터 갱신"}
        </button>
      </div>

      {helpOpen && (
        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm space-y-3">
          <p className="text-muted-foreground leading-relaxed">
            S&amp;P 500 전 종목을 <strong>5가지 팩터</strong>로 점수화해 랭킹합니다.
            모든 점수는 <strong>100점 만점의 유니버스 내 백분위</strong>이며 높을수록 우수합니다.
            왼쪽 슬라이더로 팩터 가중치를 실시간 조정하면 랭킹이 즉시 바뀝니다.
            종목을 클릭하면 레이더 차트 · 재무지표 상세 페이지로 이동합니다.
          </p>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {FACTOR_HELP.map((f) => (
              <div key={f.label} className="rounded border border-border bg-background px-3 py-2">
                <p className="font-medium text-foreground text-xs mb-0.5">{f.label}</p>
                <p className="text-muted-foreground text-xs">{f.desc}</p>
              </div>
            ))}
            <div className="rounded border border-border bg-background px-3 py-2">
              <p className="font-medium text-foreground text-xs mb-0.5">하드 필터</p>
              <p className="text-muted-foreground text-xs">200일 MA 하회 종목을 랭킹에서 완전 제외. 체크 해제 시 포함.</p>
            </div>
            <div className="rounded border border-border bg-background px-3 py-2">
              <p className="font-medium text-foreground text-xs mb-0.5">데이터 갱신</p>
              <p className="text-muted-foreground text-xs">yfinance에서 전 종목 재수집 (≈ 10분). 24시간 캐시 적용으로 당일 중복 호출은 빠름.</p>
            </div>
          </div>
        </div>
      )}

      {isLoading && <p className="text-muted-foreground text-sm">로딩 중...</p>}

      {batchStatus && batchStatus.status === "running" && (
        <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700 space-y-1.5">
          <div className="flex justify-between items-center">
            <span>{batchStatus.step}</span>
            <span className="font-data text-xs">
              {batchStatus.done} / {batchStatus.total}
            </span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: batchStatus.total > 0 ? `${Math.round(batchStatus.done / batchStatus.total * 100)}%` : "5%" }}
            />
          </div>
        </div>
      )}

      {refreshMsg && (
        <p className={`text-sm px-3 py-2 rounded border ${refreshMsg.startsWith("오류") ? "bg-red-50 border-red-200 text-red-700" : "bg-green-50 border-green-200 text-green-700"}`}>
          {refreshMsg}
        </p>
      )}
      {error && !refreshMsg && !batchStatus && (
        <p className="text-sm text-amber-600">
          데이터 없음 — &quot;데이터 갱신&quot; 버튼으로 배치 실행 후 새로고침 하세요.
        </p>
      )}

      <div className="flex gap-6 items-start">
        <FactorSidebar
          universe={universe}
          onUniverseChange={handleUniverseChange}
          weights={weights}
          onWeightsChange={setWeights}
          hardFilters={hardFilters}
          onHardFiltersChange={setHardFilters}
          sectorFilter={sectorFilter}
          onSectorChange={handleSectorChange}
          industryFilter={industryFilter}
          onIndustryChange={setIndustryFilter}
          sectors={sectors}
          industries={industries}
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
            sectorFilter={sectorFilter}
            industryFilter={industryFilter}
            topN={50}
            universe={universe}
            isBatchRunning={refreshing}
          />
        </div>
      </div>
    </div>
  );
}
