"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { Check, Eye, RefreshCw, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { candidatesApi, growthApi } from "@/lib/api";
import type { CandidateScore, GrowthTiming } from "@/lib/types";

const REGIONS = [
  ["all", "전체"],
  ["US", "미국"],
  ["KR", "국장"],
] as const;

const STATUSES = [
  ["new", "신규"],
  ["watching", "검토중"],
  ["added", "관심추가"],
  ["dismissed", "제외"],
  ["all", "전체상태"],
] as const;

const SCORE_COLUMNS = [
  ["growth_score", "성장"],
  ["quality_score", "품질"],
  ["valuation_score", "밸류"],
  ["momentum_score", "모멘텀"],
  ["timing_score", "타이밍"],
  ["liquidity_score", "유동성"],
] as const;

const DEFAULT_WEIGHTS = {
  growth: 25,
  quality: 20,
  valuation: 15,
  momentum: 20,
  timing: 15,
  liquidity: 5,
};

const PRESETS = {
  balanced: { label: "균형형", weights: DEFAULT_WEIGHTS },
  growth: { label: "성장 우선", weights: { growth: 40, quality: 20, valuation: 10, momentum: 15, timing: 10, liquidity: 5 } },
  value: { label: "밸류 우선", weights: { growth: 15, quality: 20, valuation: 35, momentum: 10, timing: 15, liquidity: 5 } },
  timing: { label: "타이밍 우선", weights: { growth: 20, quality: 15, valuation: 10, momentum: 20, timing: 30, liquidity: 5 } },
  pullback: { label: "눌림 대기형", weights: { growth: 25, quality: 20, valuation: 10, momentum: 10, timing: 30, liquidity: 5 } },
  custom: { label: "직접 설정", weights: DEFAULT_WEIGHTS },
} as const;

const SOURCES = [
  ["all", "전체 유니버스"],
  ["russell1000", "Russell 1000"],
  ["sp500", "S&P 500"],
  ["nasdaq100", "NASDAQ 100"],
  ["kospi200", "KOSPI 200"],
  ["kosdaq150", "KOSDAQ 150"],
] as const;

const WEIGHT_FIELDS = [
  ["growth", "성장"],
  ["quality", "품질"],
  ["valuation", "밸류"],
  ["momentum", "모멘텀"],
  ["timing", "타이밍"],
  ["liquidity", "유동성"],
] as const;

const FILTER_FIELDS = [
  ["min_growth_score", "성장 최소"],
  ["min_quality_score", "품질 최소"],
  ["min_valuation_score", "밸류 최소"],
  ["min_momentum_score", "모멘텀 최소"],
  ["min_timing_score", "타이밍 최소"],
  ["min_liquidity_score", "유동성 최소"],
  ["min_market_cap", "시총 최소"],
  ["max_forward_pe", "Fwd PER 최대"],
  ["max_peg", "PEG 최대"],
  ["min_roe", "ROE 최소"],
  ["max_rsi", "RSI 최대"],
] as const;

const FILTER_TOGGLES = [
  ["require_above_ma200", "MA200 위"],
  ["positive_eps_growth", "EPS 성장 +"],
  ["positive_revenue_growth", "매출 성장 +"],
] as const;

export default function CandidatesPage() {
  const [region, setRegion] = useState("all");
  const [sector, setSector] = useState("tech");
  const [status, setStatus] = useState("new");
  const [source, setSource] = useState("all");
  const [limit, setLimit] = useState("50");
  const [preset, setPreset] = useState<keyof typeof PRESETS>("balanced");
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filterToggles, setFilterToggles] = useState<Record<string, boolean>>({});
  const [excludeWatchlist, setExcludeWatchlist] = useState(true);
  const [selected, setSelected] = useState<CandidateScore | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const numericWeights = useMemo(
    () => Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, Number(value) || 0])),
    [weights],
  );
  const numericFilters = useMemo(
    () => Object.fromEntries(
      [
        ...Object.entries(filters).map(([key, value]) => [key, value === "" ? null : Number(value)]),
        ...Object.entries(filterToggles).map(([key, value]) => [key, value]),
      ],
    ),
    [filters, filterToggles],
  );
  const activeFilterCount = Object.values(filters).filter((value) => value !== "").length
    + Object.values(filterToggles).filter(Boolean).length;
  const weightTotal = Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0);
  const querySignature = JSON.stringify({ numericWeights, numericFilters, excludeWatchlist, source });
  const key = `/api/candidates?region=${region}&sector=${sector}&status=${status}&source=${source}&limit=${limit}&${querySignature}`;
  const { data = [], isLoading, error, mutate } = useSWR(key, () =>
    candidatesApi.list({
      region,
      sector,
      status,
      source,
      limit: Number(limit),
      excludeWatchlist,
      weights: numericWeights,
      filters: numericFilters,
    }),
  );
  const { data: selectedTiming } = useSWR(
    selected ? `/api/growth/ticker/${selected.ticker}/timing` : null,
    () => growthApi.timing(selected!.ticker),
  );

  const summary = useMemo(() => {
    const us = data.filter((row) => row.region === "US").length;
    const kr = data.filter((row) => row.region === "KR").length;
    return { total: data.length, us, kr };
  }, [data]);

  const refresh = async () => {
    setRefreshing(true);
    setMessage(null);
    try {
      const result = await candidatesApi.refresh(region);
      setMessage(`후보 점수 갱신 완료: ${result.rows}개`);
      await mutate();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  };

  const mark = async (row: CandidateScore, nextStatus: "watching" | "dismissed") => {
    await candidatesApi.updateStatus(row.ticker, {
      universe_group: row.universe_group,
      status: nextStatus,
    });
    setMessage(`${row.ticker} 상태를 ${nextStatus === "watching" ? "검토중" : "제외"}로 변경했습니다.`);
    await mutate();
  };

  const addWatchlist = async (row: CandidateScore) => {
    const result = await candidatesApi.addWatchlist(row.ticker, row.universe_group);
    setMessage(`${row.ticker}를 관심종목에 추가했습니다. (${result.universe})`);
    await mutate();
  };

  const applyPreset = (value: keyof typeof PRESETS) => {
    setPreset(value);
    if (value === "custom") return;
    setWeights(PRESETS[value].weights);
  };

  const updateWeight = (key: keyof typeof DEFAULT_WEIGHTS, value: string) => {
    setPreset("custom");
    setWeights((prev) => ({ ...prev, [key]: Math.max(0, Number(value) || 0) }));
  };

  const updateFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetScoring = () => {
    setPreset("balanced");
    setWeights(DEFAULT_WEIGHTS);
    setFilters({});
    setFilterToggles({});
    setExcludeWatchlist(true);
    setSource("all");
  };

  return (
    <div className="space-y-4">
      <header className="rounded-lg border border-border bg-card px-5 py-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-data text-[10px] tracking-[0.24em] text-primary">CANDIDATE SCREENER</p>
            <h1 className="mt-2 font-heading text-2xl font-medium tracking-tight">후보발굴</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              성장주 배치 점수를 통합해 관심종목에 넣기 전 후보를 압축합니다. 관심종목과 제외/검토중 종목은 기본 후보에서 빠집니다.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={refresh} disabled={refreshing}>
              <RefreshCw className={refreshing ? "animate-spin" : ""} />
              점수 갱신
            </Button>
          </div>
        </div>
      </header>

      <section className="rounded-lg border border-border bg-card px-4 py-3">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="flex flex-wrap items-center gap-2">
            <Segmented value={region} onChange={setRegion} items={REGIONS} />
            <Segmented value={status} onChange={setStatus} items={STATUSES} />
            <button
              type="button"
              onClick={() => setExcludeWatchlist((value) => !value)}
              className={`rounded-md border px-3 py-2 text-xs transition-colors ${
                excludeWatchlist
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              관심종목 제외
            </button>
            <Select value={source} onValueChange={(value) => value && setSource(value)}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SOURCES.map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sector} onValueChange={(value) => value && setSector(value)}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="tech">기술주 우선</SelectItem>
                <SelectItem value="all">전체 섹터</SelectItem>
              </SelectContent>
            </Select>
            <Select value={limit} onValueChange={(value) => value && setLimit(value)}>
              <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="30">30개</SelectItem>
                <SelectItem value="50">50개</SelectItem>
                <SelectItem value="100">100개</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-2 font-data text-xs text-muted-foreground">
            <span>전체 {summary.total}</span>
            <span>US {summary.us}</span>
            <span>KR {summary.kr}</span>
            <span>조건 {activeFilterCount}</span>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card px-4 py-3">
        <div className="grid gap-4 xl:grid-cols-[260px_1fr]">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-sm font-medium">점수 프리셋</h2>
              <Button variant="ghost" size="sm" onClick={resetScoring}>초기화</Button>
            </div>
            <Select value={preset} onValueChange={(value) => value && applyPreset(value as keyof typeof PRESETS)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(PRESETS).map(([value, item]) => (
                  <SelectItem key={value} value={value}>{item.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              합계 {weightTotal}. 가중치 합계가 100이 아니어도 자동 정규화해서 Rank를 다시 계산합니다.
            </p>
          </div>
          <div className="grid gap-4 2xl:grid-cols-[1.1fr_1fr]">
            <div>
              <h3 className="mb-2 text-xs font-medium text-muted-foreground">가중치</h3>
              <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
                {WEIGHT_FIELDS.map(([key, label]) => (
                  <label key={key} className="space-y-1">
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <input
                      className="h-9 w-full rounded-md border border-border bg-background px-2 text-right font-data text-sm outline-none focus:border-primary"
                      inputMode="decimal"
                      value={weights[key]}
                      onChange={(event) => updateWeight(key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium text-muted-foreground">조건 필터</h3>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs text-muted-foreground">비워두면 조건을 적용하지 않습니다.</p>
                <Button variant="ghost" size="sm" onClick={() => {
                  setFilters({});
                  setFilterToggles({});
                }}>조건 초기화</Button>
              </div>
              <div className="mb-2 flex flex-wrap gap-2">
                {FILTER_TOGGLES.map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setFilterToggles((prev) => ({ ...prev, [key]: !prev[key] }))}
                    className={`rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
                      filterToggles[key]
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="grid gap-2 sm:grid-cols-4 xl:grid-cols-5">
                {FILTER_FIELDS.map(([key, label]) => (
                  <label key={key} className="space-y-1">
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <input
                      className="h-9 w-full rounded-md border border-border bg-background px-2 text-right font-data text-sm outline-none focus:border-primary"
                      inputMode="decimal"
                      placeholder="-"
                      value={filters[key] ?? ""}
                      onChange={(event) => updateFilter(key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {message && (
        <p className="rounded border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-primary">{message}</p>
      )}
      {error && (
        <p className="rounded border border-fall/30 bg-fall/5 px-3 py-2 text-xs text-fall">
          후보 데이터를 불러오지 못했습니다. 성장주 배치와 후보 점수 갱신 작업을 먼저 실행해 주세요.
        </p>
      )}

      {selected && (
        <CandidateDetail
          row={selected}
          timing={selectedTiming}
          onClose={() => setSelected(null)}
          onAdd={() => addWatchlist(selected)}
          onWatch={() => mark(selected, "watching")}
          onDismiss={() => mark(selected, "dismissed")}
        />
      )}

      <section className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="font-heading text-base font-medium">후보 랭킹</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              중복 티커는 통합하고, 관심종목으로 승격하면 다음 신규 후보 목록에서 제외됩니다.
            </p>
          </div>
          <Search className="size-4 text-muted-foreground" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] border-collapse text-sm">
            <thead className="bg-muted/30 text-xs text-muted-foreground">
              <tr>
                <Th className="w-16">Rank</Th>
                <Th>종목</Th>
                <Th>출처</Th>
                <Th>섹터</Th>
                <Th className="text-right">종합</Th>
                {SCORE_COLUMNS.map(([, label]) => <Th key={label} className="text-right">{label}</Th>)}
                <Th>상태</Th>
                <Th className="text-right">액션</Th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={13} className="h-40 text-center text-muted-foreground">후보를 불러오는 중입니다.</td></tr>
              )}
              {!isLoading && data.length === 0 && (
                <tr><td colSpan={13} className="h-40 text-center text-muted-foreground">표시할 후보가 없습니다.</td></tr>
              )}
              {data.map((row) => (
                <tr
                  key={`${row.universe_group}-${row.ticker}`}
                  onClick={() => setSelected(row)}
                  className="cursor-pointer border-t border-border hover:bg-muted/30"
                >
                  <Td className="font-data text-muted-foreground">{row.rank ?? "-"}</Td>
                  <Td>
                    <div className="font-data text-primary">{row.ticker}</div>
                    <div className="mt-1 max-w-[220px] truncate text-xs text-muted-foreground">{row.name || "-"}</div>
                  </Td>
                  <Td>
                    <div className="font-data text-xs">{row.region}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{row.source_universes.join(", ") || row.source_universe || "-"}</div>
                  </Td>
                  <Td>
                    <div className="max-w-[220px] truncate">{row.sector || "-"}</div>
                    <div className="mt-1 max-w-[220px] truncate text-xs text-muted-foreground">{row.industry || "-"}</div>
                  </Td>
                  <Td className="text-right font-data text-base text-primary">{fmt(row.candidate_score)}</Td>
                  {SCORE_COLUMNS.map(([key]) => (
                    <Td key={key} className="text-right font-data">{fmt(row[key])}</Td>
                  ))}
                  <Td><StatusPill status={row.status || "new"} /></Td>
                  <Td>
                    <div className="flex justify-end gap-2" onClick={(event) => event.stopPropagation()}>
                      <Button variant="outline" size="sm" onClick={() => mark(row, "watching")}>
                        <Eye />
                        검토
                      </Button>
                      <Button size="sm" onClick={() => addWatchlist(row)}>
                        <Check />
                        관심
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => mark(row, "dismissed")}>
                        <X />
                        제외
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function CandidateDetail({
  row,
  timing,
  onClose,
  onAdd,
  onWatch,
  onDismiss,
}: {
  row: CandidateScore;
  timing?: GrowthTiming;
  onClose: () => void;
  onAdd: () => void;
  onWatch: () => void;
  onDismiss: () => void;
}) {
  return (
    <section className="sticky top-16 z-20 rounded-lg border border-primary/30 bg-card px-4 py-3 shadow-sm">
      <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr_auto] xl:items-start">
        <div>
          <p className="font-data text-[10px] tracking-[0.24em] text-primary">SELECTED CANDIDATE</p>
          <div className="mt-2 flex items-baseline gap-2">
            <h2 className="font-heading text-xl font-semibold">{row.ticker}</h2>
            <span className="text-sm text-muted-foreground">{row.name}</span>
            <span className="rounded-full border border-border px-2 py-0.5 font-data text-xs text-muted-foreground">
              {row.region}
            </span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {row.sector || "-"} · {row.industry || "-"} · {row.source_universes.join(", ") || row.source_universe || "-"}
          </p>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-medium text-muted-foreground">점수</h3>
            <div className="grid grid-cols-3 gap-2">
              <Metric label="종합" value={fmt(row.candidate_score)} strong />
              <Metric label="성장" value={fmt(row.growth_score)} />
              <Metric label="품질" value={fmt(row.quality_score)} />
              <Metric label="밸류" value={fmt(row.valuation_score)} />
              <Metric label="모멘텀" value={fmt(row.momentum_score)} />
              <Metric label="타이밍" value={fmt(row.timing_score)} />
            </div>
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium text-muted-foreground">TIMING / VALUATION</h3>
            <div className="grid grid-cols-3 gap-2">
              <Metric label="상태" value={timingLabel(timing)} />
              <Metric label="RSI" value={fmt(timing?.rsi14 ?? row.raw_rsi)} />
              <Metric label="MA200" value={row.above_ma200 === null ? "-" : row.above_ma200 ? "위" : "아래"} />
              <Metric label="Fwd PER" value={fmt(row.raw_forward_pe)} />
              <Metric label="PEG" value={fmt(row.raw_peg)} />
              <Metric label="ROE" value={fmt(row.raw_roe)} />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <Button size="sm" onClick={onAdd}><Check />관심</Button>
          <Button variant="outline" size="sm" onClick={onWatch}><Eye />검토</Button>
          <Button variant="ghost" size="sm" onClick={onDismiss}><X />제외</Button>
          <Button variant="ghost" size="sm" onClick={onClose}>닫기</Button>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-2 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className={`mt-1 font-data ${strong ? "text-base text-primary" : "text-sm text-foreground"}`}>{value}</div>
    </div>
  );
}

function Segmented({
  value,
  onChange,
  items,
}: {
  value: string;
  onChange: (value: string) => void;
  items: readonly (readonly [string, string])[];
}) {
  return (
    <div className="flex overflow-hidden rounded-md border border-border bg-muted/20">
      {items.map(([itemValue, label]) => (
        <button
          key={itemValue}
          type="button"
          onClick={() => onChange(itemValue)}
          className={`px-3 py-2 text-xs transition-colors ${
            value === itemValue ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const label = status === "watching" ? "검토중" : status === "dismissed" ? "제외" : status === "added" ? "관심" : "신규";
  return (
    <span className="inline-flex rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
      {label}
    </span>
  );
}

function Th({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <th className={`px-3 py-3 text-left font-medium ${className}`}>{children}</th>;
}

function Td({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <td className={`px-3 py-3 align-middle ${className}`}>{children}</td>;
}

function fmt(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(1);
}

function timingLabel(timing?: GrowthTiming) {
  if (!timing) return "-";
  if (timing.status === "suitable") return "진입후보";
  if (timing.status === "watch" && timing.aligned) return "추세확인";
  if (timing.status === "watch") return "관망";
  if (timing.status === "unsuitable") return "대기";
  return "부족";
}
