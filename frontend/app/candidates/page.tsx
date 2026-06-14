"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import useSWR from "swr";
import { Check, Eye, RefreshCw, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { candidatesApi } from "@/lib/api";
import type { CandidateScore } from "@/lib/types";

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
] as const;

export default function CandidatesPage() {
  const [region, setRegion] = useState("all");
  const [sector, setSector] = useState("tech");
  const [status, setStatus] = useState("new");
  const [limit, setLimit] = useState("50");
  const [message, setMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const key = `/api/candidates?region=${region}&sector=${sector}&status=${status}&limit=${limit}`;
  const { data = [], isLoading, error, mutate } = useSWR(key, () =>
    candidatesApi.list({ region, sector, status, limit: Number(limit) }),
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
                <tr><td colSpan={12} className="h-40 text-center text-muted-foreground">후보를 불러오는 중입니다.</td></tr>
              )}
              {!isLoading && data.length === 0 && (
                <tr><td colSpan={12} className="h-40 text-center text-muted-foreground">표시할 후보가 없습니다.</td></tr>
              )}
              {data.map((row) => (
                <tr key={`${row.universe_group}-${row.ticker}`} className="border-t border-border hover:bg-muted/30">
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
                    <div className="flex justify-end gap-2">
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
