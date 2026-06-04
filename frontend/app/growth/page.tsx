"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { Database, Filter, RefreshCw, ScanSearch, Star } from "lucide-react";

import { GrowthRankingTable } from "@/components/growth/ranking-table";
import { TimingCard } from "@/components/growth/timing-card";
import { Top10Panel } from "@/components/growth/top10-panel";
import { ValuationCard } from "@/components/growth/valuation-card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { growthApi } from "@/lib/api";

const UNIVERSES = [
  ["sp500", "S&P 500"],
  ["nasdaq100", "NASDAQ 100"],
  ["kospi200", "KOSPI 200"],
  ["kosdaq150", "KOSDAQ 150"],
];

const STEPS = [
  ["rank", "01", "전 종목 랭킹", Database],
  ["top", "02", "Top10 압축", Filter],
  ["verify", "03", "매수 검증", ScanSearch],
] as const;

type Step = (typeof STEPS)[number][0];

export default function GrowthPage() {
  const [universe, setUniverse] = useState("sp500");
  const [step, setStep] = useState<Step>("rank");
  const [sector, setSector] = useState("");
  const [cap, setCap] = useState("");
  const [signal, setSignal] = useState("");
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<{
    status: string;
    step: string;
    done: number;
    total: number;
    finished_at: string;
    latest_as_of: string;
    is_fresh: boolean;
  } | null>(null);
  const pollRef = useRef<number | null>(null);

  const { data: scores = [], isLoading, error: scoresError, mutate: mutateScores } = useSWR(
    `/api/growth/scores?universe=${universe}`,
    () => growthApi.scores(universe),
  );
  const { data: top = [], isLoading: topLoading, error: topError, mutate: mutateTop } = useSWR(
    `/api/growth/top?universe=${universe}&sector=${sector}&cap=${cap}&signal=${signal}`,
    () => growthApi.top(universe, sector, cap, signal),
  );
  const { data: watchlistStatus, mutate: mutateWatchlistStatus } = useSWR(
    selectedTicker ? `/api/growth/watchlist/${selectedTicker}?universe=${universe}` : null,
    () => growthApi.watchlistStatus(selectedTicker!, universe),
  );
  const { data: valuation, error: valuationError } = useSWR(
    selectedTicker ? `/api/growth/ticker/${selectedTicker}/valuation?universe=${universe}` : null,
    () => growthApi.valuation(selectedTicker!, universe),
  );
  const { data: timing } = useSWR(
    selectedTicker ? `/api/growth/ticker/${selectedTicker}/timing` : null,
    () => growthApi.timing(selectedTicker!),
  );

  const sectors = useMemo(
    () => [...new Set(scores.map((score) => score.sector).filter((value): value is string => Boolean(value)))].sort(),
    [scores],
  );

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const checkStatus = useCallback(async () => {
    const status = await growthApi.status(universe);
    setBatchStatus(status);
    if (status.status === "running") {
      setRefreshing(true);
      return;
    }
    stopPolling();
    setRefreshing(false);
    if (status.status === "done") {
      setMessage("배치가 완료됐습니다. 최신 점수를 표시합니다.");
      await Promise.all([mutateScores(), mutateTop()]);
    } else if (status.status === "error") {
      setMessage(`배치 오류: ${status.step}`);
    }
  }, [mutateScores, mutateTop, stopPolling, universe]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = window.setInterval(() => {
      void checkStatus();
    }, 3000);
    void checkStatus();
  }, [checkStatus, stopPolling]);

  useEffect(() => {
    const timeout = window.setTimeout(startPolling, 0);
    return () => {
      window.clearTimeout(timeout);
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  const selectFromRanking = (ticker: string) => {
    setSelectedTicker(ticker);
    setStep("top");
  };

  const selectFromTop = (ticker: string) => {
    setSelectedTicker(ticker);
    setStep("verify");
  };

  const toggleWatchlist = async () => {
    if (!selectedTicker) return;
    const isInWatchlist = watchlistStatus?.in_watchlist ?? false;
    try {
      if (isInWatchlist) {
        await growthApi.removeWatchlist(selectedTicker, universe);
        setMessage(`${selectedTicker}를 Watchlist에서 제거했습니다.`);
      } else {
        await growthApi.addWatchlist(selectedTicker, universe);
        setMessage(`${selectedTicker}를 Watchlist에 추가했습니다.`);
      }
      await mutateWatchlistStatus();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const refresh = async (force = false) => {
    setRefreshing(true);
    setMessage(null);
    try {
      const result = await growthApi.refresh(universe, force);
      if (result.status === "fresh") {
        setMessage("오늘 데이터가 이미 최신입니다.");
        await checkStatus();
        return;
      }
      setMessage(force ? "강제 갱신을 시작했습니다." : "배치를 시작했습니다. 진행 상태를 확인하고 있습니다.");
      startPolling();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-5">
      <header className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="grid gap-5 px-5 py-5 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <p className="font-data text-[10px] tracking-[0.24em] text-primary">GROWTH STOCK FINDER</p>
            <h1 className="mt-2 font-heading text-2xl font-medium tracking-tight">좋은종목찾기</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              성장성 40 · 수익성 30 · 현금창출력 20 · 재무안정성 10. 섹터 안에서 비교하고, 하드 필터로 압축한 뒤 매수 타이밍을 확인합니다.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={universe} onValueChange={(value) => {
              if (!value) return;
              setUniverse(value);
              setSelectedTicker(null);
              setStep("rank");
            }}>
              <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
              <SelectContent>
                {UNIVERSES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => refresh()} disabled={refreshing || batchStatus?.is_fresh}>
              <RefreshCw className={refreshing ? "animate-spin" : ""} />
              데이터 갱신
            </Button>
            <Button variant="ghost" size="sm" onClick={() => refresh(true)} disabled={refreshing}>
              강제 갱신
            </Button>
          </div>
        </div>
        <div className="grid border-t border-border md:grid-cols-3">
          {STEPS.map(([value, number, label, Icon]) => (
            <button
              key={value}
              type="button"
              onClick={() => setStep(value)}
              className={`flex items-center gap-3 border-b border-border px-5 py-3 text-left transition-colors md:border-b-0 md:border-r last:border-r-0 ${
                step === value ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted/50"
              }`}
            >
              <span className="font-data text-xs text-primary">{number}</span>
              <Icon className="size-4" />
              <span className="text-sm">{label}</span>
            </button>
          ))}
        </div>
      </header>

      {(batchStatus?.finished_at || batchStatus?.latest_as_of) && (
        <p className="font-data text-[11px] text-muted-foreground">
          마지막 갱신: {batchStatus.finished_at || batchStatus.latest_as_of}
          {batchStatus.is_fresh ? " · 오늘 데이터 최신" : ""}
        </p>
      )}

      {message && <p className="rounded border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">{message}</p>}
      {scoresError && (
        <p className="rounded border border-fall/30 bg-fall/5 px-3 py-2 text-xs text-fall">
          성장 점수를 불러오지 못했습니다. 데이터 갱신 상태를 확인해 주세요.
        </p>
      )}

      {batchStatus?.status === "running" && (
        <section className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="text-foreground">{batchStatus.step || "배치 실행 중"}</span>
            <span className="font-data text-muted-foreground">{batchStatus.done} / {batchStatus.total}</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: batchStatus.total > 0 ? `${Math.max(2, Math.round(batchStatus.done / batchStatus.total * 100))}%` : "2%" }}
            />
          </div>
        </section>
      )}

      {step === "rank" && (
        <section className="rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <p className="text-sm font-medium">섹터 상대평가 랭킹</p>
              <p className="mt-1 text-xs text-muted-foreground">종목을 선택하면 Top10 압축 단계로 이동합니다.</p>
            </div>
            <span className="font-data text-xs text-muted-foreground">{scores.length} 종목</span>
          </div>
          {isLoading ? <p className="p-8 text-center text-sm text-muted-foreground">점수를 불러오는 중입니다.</p> : (
            <GrowthRankingTable scores={scores} selectedTicker={selectedTicker} onSelect={selectFromRanking} />
          )}
        </section>
      )}

      {step === "top" && (
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Top10 하드 필터</p>
              <p className="mt-1 text-xs text-muted-foreground">부채, FCF, OCF, 유동비율, 섹터 평균 마진을 모두 통과한 종목입니다.</p>
            </div>
            <div className="flex gap-2">
              <Select value={sector || "all"} onValueChange={(value) => setSector(!value || value === "all" ? "" : value)}>
                <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 섹터</SelectItem>
                  {sectors.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={cap || "all"} onValueChange={(value) => setCap(!value || value === "all" ? "" : value)}>
                <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 시총</SelectItem>
                  <SelectItem value="large">Large</SelectItem>
                  <SelectItem value="mid">Mid</SelectItem>
                  <SelectItem value="small">Small</SelectItem>
                </SelectContent>
              </Select>
              <Select value={signal || "all"} onValueChange={(value) => setSignal(!value || value === "all" ? "" : value)}>
                <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 신호</SelectItem>
                  <SelectItem value="aligned">상승 추세</SelectItem>
                  <SelectItem value="pullback">눌림목 접근</SelectItem>
                  <SelectItem value="volume">거래량 확인</SelectItem>
                  <SelectItem value="suitable">매수 적합</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="mt-4">
            {topError ? <p className="py-12 text-center text-sm text-fall">Top10 데이터를 불러오지 못했습니다.</p> : topLoading ? <p className="py-12 text-center text-sm text-muted-foreground">Top10을 압축하는 중입니다.</p> : (
              <Top10Panel scores={top} selectedTicker={selectedTicker} onSelect={selectFromTop} />
            )}
          </div>
        </section>
      )}

      {step === "verify" && (
        <section>
          {!selectedTicker ? (
            <div className="rounded-xl border border-dashed border-border px-5 py-16 text-center text-sm text-muted-foreground">
              랭킹 또는 Top10에서 검증할 종목을 선택하세요.
            </div>
          ) : (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-baseline gap-3">
                  <h2 className="font-data text-xl text-foreground">{selectedTicker}</h2>
                  <span className="text-xs text-muted-foreground">적정가와 매수 타이밍 교차 검증</span>
                </div>
                <Button variant="outline" size="sm" onClick={toggleWatchlist}>
                  <Star className={watchlistStatus?.in_watchlist ? "fill-primary text-primary" : ""} />
                  {watchlistStatus?.in_watchlist ? "Watchlist에서 제거" : "Watchlist에 추가"}
                </Button>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <ValuationCard data={valuation} error={valuationError} />
                <TimingCard data={timing} />
              </div>
            </>
          )}
        </section>
      )}

    </div>
  );
}
