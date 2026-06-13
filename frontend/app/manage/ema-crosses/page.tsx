"use client";

import { Activity, History, Play, RefreshCw, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { goldenCrossApi, jobsApi } from "@/lib/api";
import type { GoldenCrossActive, GoldenCrossHistory } from "@/lib/types";

const GROUPS = [
  { key: "all", label: "전체" },
  { key: "KOSPI", label: "코스피" },
  { key: "KOSDAQ", label: "코스닥" },
  { key: "US", label: "미장" },
];

const statusLabels: Record<string, string> = {
  NEW: "신규",
  MAINTAINED: "유지",
  EXPIRED: "제외",
  BROKEN: "종료",
};

const statusClass: Record<string, string> = {
  NEW: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  MAINTAINED: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  EXPIRED: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-200",
  BROKEN: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-200",
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" });
}

function formatNumber(value: number | null) {
  if (value == null) return "-";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function groupLabel(value: string | null) {
  if (value === "KOSPI") return "코스피";
  if (value === "KOSDAQ") return "코스닥";
  if (value === "US") return "미장";
  return value ?? "-";
}

export default function EmaCrossesPage() {
  const [group, setGroup] = useState("all");
  const [running, setRunning] = useState<string | null>(null);
  const { data, mutate, isLoading } = useSWR(
    `/api/golden-cross?group=${group}`,
    () => goldenCrossApi.list(group, 300),
    { refreshInterval: 30_000 },
  );
  const active = data?.active ?? [];
  const history = data?.history ?? [];

  const metrics = useMemo(() => ({
    active: active.length,
    newToday: history.filter((row) => row.status === "NEW" && isToday(row.checked_at)).length,
    expired: history.filter((row) => row.status === "EXPIRED").length,
    broken: history.filter((row) => row.status === "BROKEN").length,
  }), [active, history]);

  const runJob = async (jobId: "ema_scan_kr" | "ema_scan_us") => {
    setRunning(jobId);
    try {
      await jobsApi.run(jobId);
      setTimeout(() => mutate(), 1500);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="space-y-6">
      <header className="border border-border bg-card px-5 py-5">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <TrendingUp className="h-4 w-4" />
          EMA Golden Cross
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground">EMA 골든크로스</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          신규, 유지, 5일 이상 제외, 종료 이력을 확인합니다. Telegram 발송 대상과 웹 기록은 같은 스캔 결과를 기준으로 합니다.
        </p>
      </header>

      <section className="grid gap-3 sm:grid-cols-4">
        <Metric label="현재 활성" value={metrics.active} />
        <Metric label="오늘 신규" value={metrics.newToday} />
        <Metric label="5일 이상 제외" value={metrics.expired} />
        <Metric label="크로스 종료" value={metrics.broken} />
      </section>

      <section className="border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex flex-wrap gap-2">
            {GROUPS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setGroup(item.key)}
                className={`border px-3 py-1.5 text-xs transition-colors ${
                  group === item.key
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:border-primary hover:text-foreground"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => runJob("ema_scan_kr")}
              disabled={running !== null}
              className="inline-flex h-9 items-center gap-2 border border-border bg-background px-3 text-xs text-foreground hover:border-primary disabled:opacity-50"
            >
              {running === "ema_scan_kr" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              국장 스캔
            </button>
            <button
              type="button"
              onClick={() => runJob("ema_scan_us")}
              disabled={running !== null}
              className="inline-flex h-9 items-center gap-2 border border-border bg-background px-3 text-xs text-foreground hover:border-primary disabled:opacity-50"
            >
              {running === "ema_scan_us" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              미장 스캔
            </button>
          </div>
        </div>

        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="border-b border-border xl:border-b-0 xl:border-r">
            <PanelTitle icon={<Activity className="h-4 w-4" />} title="현재 활성" description="5일 미만으로 추적 중인 EMA 골든크로스입니다." />
            <ActiveTable rows={active} loading={isLoading} />
          </div>
          <div>
            <PanelTitle icon={<History className="h-4 w-4" />} title="상태 이력" description="신규, 유지, 제외, 종료 이벤트를 최신순으로 기록합니다." />
            <HistoryTable rows={history} loading={isLoading} />
          </div>
        </div>
      </section>
    </div>
  );
}

function isToday(value: string) {
  const d = new Date(value);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-2 font-data text-2xl font-semibold text-foreground">{value.toLocaleString("ko-KR")}</p>
    </div>
  );
}

function PanelTitle({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return (
    <div className="border-b border-border px-4 py-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <span className="text-primary">{icon}</span>
        {title}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </div>
  );
}

function ActiveTable({ rows, loading }: { rows: GoldenCrossActive[]; loading: boolean }) {
  if (loading) return <Empty text="불러오는 중..." />;
  if (!rows.length) return <Empty text="현재 활성 골든크로스가 없습니다." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-border bg-muted/30 text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">종목</th>
            <th className="px-3 py-3 font-medium">그룹</th>
            <th className="px-3 py-3 font-medium">일차</th>
            <th className="px-3 py-3 font-medium">최초 감지</th>
            <th className="px-3 py-3 font-medium">마지막 확인</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ticker} className="border-b border-border last:border-0">
              <td className="px-4 py-3">
                <div className="font-medium text-foreground">{row.name || row.ticker}</div>
                <div className="font-data text-xs text-muted-foreground">{row.ticker}</div>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{groupLabel(row.group_name)}</td>
              <td className="px-3 py-3 font-data text-foreground">{row.day_count}일차</td>
              <td className="px-3 py-3 font-data text-xs text-muted-foreground">{formatDate(row.first_detected_at)}</td>
              <td className="px-3 py-3 font-data text-xs text-muted-foreground">{formatDate(row.last_sent_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryTable({ rows, loading }: { rows: GoldenCrossHistory[]; loading: boolean }) {
  if (loading) return <Empty text="불러오는 중..." />;
  if (!rows.length) return <Empty text="상태 이력이 없습니다." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[920px] text-left text-sm">
        <thead className="border-b border-border bg-muted/30 text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">시간</th>
            <th className="px-3 py-3 font-medium">상태</th>
            <th className="px-3 py-3 font-medium">종목</th>
            <th className="px-3 py-3 font-medium">그룹</th>
            <th className="px-3 py-3 font-medium">일차</th>
            <th className="px-3 py-3 font-medium">현재가</th>
            <th className="px-3 py-3 font-medium">EMA</th>
            <th className="px-3 py-3 font-medium">사유</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0">
              <td className="px-4 py-3 font-data text-xs text-muted-foreground">{formatDate(row.checked_at)}</td>
              <td className="px-3 py-3">
                <span className={`inline-flex border px-2 py-1 text-xs ${statusClass[row.status] ?? "border-border bg-muted text-muted-foreground"}`}>
                  {statusLabels[row.status] ?? row.status}
                </span>
              </td>
              <td className="px-3 py-3">
                <div className="font-medium text-foreground">{row.name || row.ticker}</div>
                <div className="font-data text-xs text-muted-foreground">{row.ticker}</div>
              </td>
              <td className="px-3 py-3 text-muted-foreground">{groupLabel(row.group_name)}</td>
              <td className="px-3 py-3 font-data text-foreground">{row.day_count ? `${row.day_count}일차` : "-"}</td>
              <td className="px-3 py-3 font-data text-foreground">{formatNumber(row.close)}</td>
              <td className="px-3 py-3 font-data text-xs text-muted-foreground">
                {formatNumber(row.ema5)} / {formatNumber(row.ema20)} / {formatNumber(row.ema60)}
              </td>
              <td className="px-3 py-3 text-xs text-muted-foreground">{row.reason ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="px-4 py-12 text-center text-sm text-muted-foreground">{text}</div>;
}
