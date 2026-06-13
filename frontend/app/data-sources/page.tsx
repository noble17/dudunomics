import { Activity, ArrowRightLeft, Database, FileText, KeyRound, Route } from "lucide-react";
import type { ReactNode } from "react";
import {
  dataSourceEntries,
  providerInventory,
  sourceStatusLabels,
  type DataSourceStatus,
} from "@/lib/data-sources";

const statusClasses: Record<DataSourceStatus, string> = {
  active: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  fallback: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-200",
  planned: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
};

export default function DataSourcesPage() {
  const activeCount = dataSourceEntries.filter((entry) => entry.status === "active").length;
  const plannedCount = dataSourceEntries.filter((entry) => entry.status === "planned").length;
  const authCount = providerInventory.filter((provider) => provider.auth !== "없음").length;

  return (
    <div className="space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="border border-border bg-card px-6 py-6 shadow-sm">
          <div className="flex items-center gap-3 text-sm font-medium text-primary">
            <Database className="h-4 w-4" />
            Dudunomics Data Map
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground">
            데이터 출처 인벤토리
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            현재 화면과 API가 의존하는 provider를 기능별로 정리했습니다. Toss OpenAPI 전환 후보는 기존 provider를 유지한 채 병렬로 붙이는 방향으로 표시했습니다.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Metric label="기능 영역" value={dataSourceEntries.length} icon={<Route className="h-4 w-4" />} />
          <Metric label="사용 중" value={activeCount} icon={<Activity className="h-4 w-4" />} />
          <Metric label="인증 필요" value={authCount} icon={<KeyRound className="h-4 w-4" />} />
          <Metric label="Provider" value={providerInventory.length} icon={<Database className="h-4 w-4" />} />
          <Metric label="Toss 후보" value={plannedCount} icon={<ArrowRightLeft className="h-4 w-4" />} />
          <div className="flex min-h-28 flex-col justify-between border border-border bg-card p-4 text-sm">
            <FileText className="h-4 w-4 text-primary" />
            <span className="font-medium text-foreground">문서 위치</span>
            <span className="font-data text-xs text-muted-foreground">docs/data-sources.md</span>
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">기능별 흐름</h2>
            <p className="mt-1 text-sm text-muted-foreground">화면, 데이터, 코드 경로, Toss 적용성을 함께 봅니다.</p>
          </div>
        </div>
        <div className="overflow-x-auto border border-border bg-card">
          <div className="min-w-[980px]">
            <div className="grid grid-cols-[1.05fr_1.15fr_1.2fr_1.25fr] border-b border-border bg-muted/30 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span>영역</span>
              <span>데이터</span>
              <span>현재 출처</span>
              <span>Toss 적용성</span>
            </div>
            {dataSourceEntries.map((entry) => (
              <div
                key={entry.area}
                className="grid grid-cols-[1.05fr_1.15fr_1.2fr_1.25fr] gap-4 border-b border-border px-4 py-4 last:border-b-0"
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-foreground">{entry.area}</h3>
                    <span className={`border px-2 py-0.5 text-[11px] font-medium ${statusClasses[entry.status]}`}>
                      {sourceStatusLabels[entry.status]}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {entry.surfaces.map((surface) => (
                      <span key={surface} className="border border-border bg-background px-2 py-1 font-data text-[11px] text-muted-foreground">
                        {surface}
                      </span>
                    ))}
                  </div>
                </div>
                <p className="text-sm leading-6 text-foreground">{entry.data}</p>
                <div className="space-y-2 text-sm leading-6">
                  <p className="text-foreground">{entry.primary}</p>
                  <p className="text-muted-foreground">Fallback: {entry.fallback}</p>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {entry.code.map((path) => (
                      <span key={path} className="bg-muted px-2 py-1 font-data text-[11px] text-muted-foreground">
                        {path}
                      </span>
                    ))}
                  </div>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">{entry.tossFit}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-foreground">Provider 목록</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {providerInventory.map((provider) => (
            <article key={provider.name} className="border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground">{provider.name}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{provider.role}</p>
                </div>
                <span className="shrink-0 border border-border bg-background px-2 py-1 font-data text-[11px] text-muted-foreground">
                  {provider.auth}
                </span>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">{provider.notes}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {provider.code.map((path) => (
                  <span key={path} className="bg-muted px-2 py-1 font-data text-[11px] text-muted-foreground">
                    {path}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
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
