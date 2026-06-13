"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Play,
  RotateCw,
  TimerReset,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { jobsApi } from "@/lib/api";
import type { JobOut, JobRun } from "@/lib/types";

const statusLabels: Record<string, string> = {
  running: "실행 중",
  success: "성공",
  failed: "실패",
  skipped: "건너뜀",
};

const statusClasses: Record<string, string> = {
  running: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  failed: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-200",
  skipped: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-200",
};

export default function JobsPage() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [runningBootstrap, setRunningBootstrap] = useState(false);
  const { data: jobs = [], mutate, isLoading } = useSWR("/api/jobs", jobsApi.list, {
    refreshInterval: 15_000,
  });
  const categories = useMemo(
    () => ["all", ...Array.from(new Set(jobs.map((job) => job.category)))],
    [jobs],
  );
  const filteredJobs = useMemo(
    () => jobs.filter((job) => selectedCategory === "all" || job.category === selectedCategory),
    [jobs, selectedCategory],
  );
  const bootstrapJobs = useMemo(() => jobs.filter((job) => job.bootstrap), [jobs]);
  const activeJobId = selectedJobId ?? filteredJobs[0]?.id ?? jobs[0]?.id ?? "";
  const activeJob = jobs.find((job) => job.id === activeJobId) ?? null;
  const { data: runs = [], mutate: mutateRuns } = useSWR(
    activeJobId ? `/api/jobs/${activeJobId}/runs` : null,
    () => jobsApi.runs(activeJobId, 50),
    { refreshInterval: 15_000 },
  );

  const metrics = useMemo(() => {
    const latest = jobs.map((job) => job.latest_run).filter(Boolean) as JobRun[];
    const bootstrapReady = jobs.filter((job) => job.bootstrap && job.latest_run?.status === "success").length;
    return {
      total: jobs.length,
      running: latest.filter((run) => run.status === "running").length,
      failed: latest.filter((run) => run.status === "failed").length,
      success: latest.filter((run) => run.status === "success").length,
      bootstrapReady,
    };
  }, [jobs]);

  const runJob = async (jobId: string) => {
    setRunningJobId(jobId);
    try {
      await jobsApi.run(jobId);
      await mutate();
      if (jobId === activeJobId) await mutateRuns();
    } finally {
      setRunningJobId(null);
    }
  };

  const runBootstrap = async () => {
    setRunningBootstrap(true);
    try {
      await jobsApi.runBootstrap();
      await mutate();
      if (activeJobId) await mutateRuns();
    } finally {
      setRunningBootstrap(false);
    }
  };

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">작업 목록을 불러오는 중...</div>;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[1fr_560px]">
        <div className="border border-border bg-card px-5 py-5">
          <div className="flex items-center gap-2 text-sm font-medium text-primary">
            <Activity className="h-4 w-4" />
            Backend Jobs
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground">작업관리</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            백엔드에서 주기 실행되는 스냅샷, 알림, EMA 스캔, 성장주 배치, Toss 동기화 작업의 최근 상태를 확인하고 필요할 때 수동 실행합니다.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Metric label="등록 작업" value={metrics.total} icon={<Clock3 className="h-4 w-4" />} />
          <Metric label="실행 중" value={metrics.running} icon={<RotateCw className="h-4 w-4" />} />
          <Metric label="최근 성공" value={metrics.success} icon={<CheckCircle2 className="h-4 w-4" />} />
          <Metric label="최근 실패" value={metrics.failed} icon={<AlertTriangle className="h-4 w-4" />} />
          <Metric label="초기 완료" value={metrics.bootstrapReady} icon={<TimerReset className="h-4 w-4" />} />
        </div>
      </section>

      <section className="border border-border bg-card">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-primary">
              <TimerReset className="h-4 w-4" />
              Initial Backfill
            </div>
            <h2 className="mt-2 font-semibold text-foreground">초기 데이터 적재</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              첫 배포나 데이터 초기화 직후 먼저 실행할 작업입니다. 화면 조회는 DB/cache를 우선 사용하므로, 여기서 필요한 데이터를 명시적으로 채웁니다.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="border border-border bg-background px-3 py-1.5 font-data text-xs text-muted-foreground">
              {metrics.bootstrapReady}/{bootstrapJobs.length} 완료
            </span>
            <button
              type="button"
              onClick={runBootstrap}
              disabled={runningBootstrap || runningJobId !== null}
              className="inline-flex h-9 items-center gap-2 border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {runningBootstrap ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              전체 실행
            </button>
          </div>
        </div>
        <div className="grid gap-0 lg:grid-cols-2 2xl:grid-cols-3">
          {bootstrapJobs.map((job) => (
            <BootstrapJobCard
              key={job.id}
              job={job}
              selected={job.id === activeJobId}
              running={runningJobId === job.id}
              onSelect={() => setSelectedJobId(job.id)}
              onRun={() => runJob(job.id)}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_520px]">
        <div className="border border-border bg-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">등록 작업</h2>
              <p className="mt-1 text-xs text-muted-foreground">스케줄러에 등록된 작업과 최근 실행 결과입니다.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map((category) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => {
                    setSelectedCategory(category);
                    setSelectedJobId(null);
                  }}
                  className={`border px-3 py-1.5 text-xs transition-colors ${
                    selectedCategory === category
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-primary hover:text-foreground"
                  }`}
                >
                  {category === "all" ? "전체" : category}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[980px]">
              <div className="grid grid-cols-[1.15fr_0.6fr_0.75fr_0.85fr_0.85fr_1.1fr_0.42fr] border-b border-border bg-muted/30 px-4 py-3 text-xs font-semibold text-muted-foreground">
                <span>작업</span>
                <span>분류</span>
                <span>스케줄</span>
                <span>예상 다음 실행</span>
                <span>최근 실행</span>
                <span>메시지</span>
                <span />
              </div>
              {filteredJobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  selected={job.id === activeJobId}
                  running={runningJobId === job.id}
                  onSelect={() => setSelectedJobId(job.id)}
                  onRun={() => runJob(job.id)}
                />
              ))}
              {filteredJobs.length === 0 && (
                <div className="px-4 py-12 text-center text-sm text-muted-foreground">표시할 작업이 없습니다.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <JobDetail job={activeJob} running={runningJobId === activeJobId} onRun={() => activeJobId && runJob(activeJobId)} />
          <div className="border border-border bg-card">
            <div className="border-b border-border px-4 py-4">
              <h2 className="font-semibold text-foreground">최근 실행 이력</h2>
              <p className="mt-1 font-data text-xs text-muted-foreground">{activeJobId || "-"}</p>
            </div>
            <div className="max-h-[620px] overflow-y-auto">
              {runs.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-muted-foreground">아직 실행 이력이 없습니다.</div>
              ) : (
                runs.map((run) => <RunItem key={run.id} run={run} />)
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function JobRow({
  job,
  selected,
  running,
  onSelect,
  onRun,
}: {
  job: JobOut;
  selected: boolean;
  running: boolean;
  onSelect: () => void;
  onRun: () => void;
}) {
  const latest = job.latest_run;
  return (
    <div
      className={`grid grid-cols-[1.15fr_0.6fr_0.75fr_0.85fr_0.85fr_1.1fr_0.42fr] items-center gap-4 border-b border-border px-4 py-4 text-sm last:border-b-0 ${
        selected ? "bg-primary/5" : ""
      }`}
    >
      <button type="button" onClick={onSelect} className="text-left">
        <div className="font-semibold text-foreground">{job.name}</div>
        <div className="mt-1 text-xs leading-5 text-muted-foreground">{job.description}</div>
      </button>
      <span className="w-fit border border-border bg-background px-2 py-1 font-data text-xs text-muted-foreground">
        {job.category}
      </span>
      <span className="text-muted-foreground">{job.schedule}</span>
      <span className="font-data text-xs text-muted-foreground">{nextRunLabel(job.schedule)}</span>
      <div className="space-y-1">
        <StatusBadge status={latest?.status ?? "none"} />
        <div className="font-data text-xs text-muted-foreground">{formatDate(latest?.started_at)}</div>
      </div>
      <span className="truncate text-muted-foreground" title={latest?.error ?? latest?.message ?? ""}>
        {latest?.error ?? latest?.message ?? "-"}
      </span>
      <button
        type="button"
        onClick={onRun}
        disabled={running || latest?.status === "running"}
        className="inline-flex h-9 w-9 items-center justify-center border border-border bg-background text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
        title="수동 실행"
      >
        {running ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
      </button>
    </div>
  );
}

function JobDetail({
  job,
  running,
  onRun,
}: {
  job: JobOut | null;
  running: boolean;
  onRun: () => void;
}) {
  if (!job) {
    return (
      <div className="border border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
        작업을 선택하세요.
      </div>
    );
  }

  const latest = job.latest_run;
  const meta = latest?.meta_json ?? {};
  const metaEntries = Object.entries(meta);

  return (
    <div className="border border-border bg-card">
      <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-4">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <Database className="h-4 w-4" />
            <span className="font-data text-xs">{job.id}</span>
          </div>
          <h2 className="mt-2 font-semibold text-foreground">{job.name}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{job.description}</p>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={running || latest?.status === "running"}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-border bg-background text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
          title="수동 실행"
        >
          {running ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        </button>
      </div>

      <div className="grid grid-cols-2 border-b border-border">
        <DetailCell label="분류" value={job.category} />
        <DetailCell label="스케줄" value={job.schedule} />
        <DetailCell label="예상 다음 실행" value={nextRunLabel(job.schedule)} />
        <DetailCell label="최근 실행" value={formatDate(latest?.started_at)} />
      </div>

      <div className="px-4 py-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-muted-foreground">최근 결과</span>
          <StatusBadge status={latest?.status ?? "none"} />
        </div>
        <p className="min-h-10 text-sm leading-6 text-foreground">{latest?.error ?? latest?.message ?? "-"}</p>
        {metaEntries.length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-2">
            {metaEntries.slice(0, 6).map(([key, value]) => (
              <div key={key} className="border border-border bg-background px-3 py-2">
                <div className="font-data text-[10px] text-muted-foreground">{key}</div>
                <div className="mt-1 truncate font-data text-xs text-foreground" title={String(value)}>
                  {String(value)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BootstrapJobCard({
  job,
  selected,
  running,
  onSelect,
  onRun,
}: {
  job: JobOut;
  selected: boolean;
  running: boolean;
  onSelect: () => void;
  onRun: () => void;
}) {
  const latest = job.latest_run;
  const isReady = latest?.status === "success";
  return (
    <div
      className={`border-b border-border px-4 py-4 lg:border-r 2xl:[&:nth-child(3n)]:border-r-0 lg:[&:nth-child(2n)]:border-r-0 2xl:[&:nth-child(2n)]:border-r ${
        selected ? "bg-primary/5" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={onSelect} className="min-w-0 text-left">
          <div className="flex items-center gap-2">
            <StatusDot status={latest?.status ?? "none"} />
            <p className="truncate text-sm font-semibold text-foreground">{job.name}</p>
          </div>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {job.bootstrap_description ?? job.description}
          </p>
        </button>
        <button
          type="button"
          onClick={onRun}
          disabled={running || latest?.status === "running"}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center border border-border bg-background text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
          title="수동 실행"
        >
          {running ? <RotateCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        </button>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="font-data text-xs text-muted-foreground">{formatDate(latest?.started_at)}</span>
        <span className={`text-xs ${isReady ? "text-emerald-300" : "text-muted-foreground"}`}>
          {isReady ? "적재됨" : "적재 필요"}
        </span>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "success"
      ? "bg-emerald-400"
      : status === "failed"
        ? "bg-red-400"
        : status === "running"
          ? "bg-sky-400"
          : "bg-muted-foreground";
  return <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />;
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-b border-border px-4 py-3 even:border-r-0 [&:nth-last-child(-n+2)]:border-b-0">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 font-data text-xs text-foreground">{value}</div>
    </div>
  );
}

function RunItem({ run }: { run: JobRun }) {
  return (
    <div className="border-b border-border px-4 py-4 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <StatusBadge status={run.status} />
        <span className="font-data text-xs text-muted-foreground">{formatDuration(run.duration_ms)}</span>
      </div>
      <div className="mt-3 font-data text-xs text-muted-foreground">
        {formatDate(run.started_at)} · {run.trigger_type}
      </div>
      <p className="mt-2 text-sm leading-5 text-foreground">{run.error ?? run.message ?? "-"}</p>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="flex min-h-28 flex-col justify-between border border-border bg-card p-4">
      <div className="text-primary">{icon}</div>
      <div>
        <div className="font-data text-2xl text-foreground">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "none") {
    return <span className="border border-border bg-background px-2 py-1 text-xs text-muted-foreground">이력 없음</span>;
  }
  return (
    <span className={`w-fit border px-2 py-1 text-xs font-medium ${statusClasses[status] ?? statusClasses.skipped}`}>
      {statusLabels[status] ?? status}
    </span>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(value?: number | null) {
  if (value == null) return "-";
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

function nextRunLabel(schedule: string) {
  const now = new Date();
  const interval = schedule.match(/^(\d+)분마다$/);
  if (interval) {
    const minutes = Number(interval[1]);
    const next = new Date(now.getTime() + minutes * 60_000);
    return formatDate(next.toISOString());
  }

  const cron = schedule.match(/매일\s+(\d{1,2}):(\d{2})\s+KST/);
  if (cron) {
    const next = new Date(now);
    next.setHours(Number(cron[1]), Number(cron[2]), 0, 0);
    if (next <= now) next.setDate(next.getDate() + 1);
    return formatDate(next.toISOString());
  }

  return "-";
}
