import { Layers3, Route } from "lucide-react";
import {
  uiMigrationEntries,
  uiMigrationStatusLabels,
  type UiMigrationStatus,
} from "@/lib/ui-migration";

const statusClasses: Record<UiMigrationStatus, string> = {
  absorbed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  partial: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  todo: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-200",
  retire: "border-muted bg-muted text-muted-foreground",
  removed: "border-zinc-500/30 bg-zinc-500/10 text-zinc-700 dark:text-zinc-200",
};

export default function UiMigrationPage() {
  const counts = uiMigrationEntries.reduce(
    (acc, entry) => ({ ...acc, [entry.status]: acc[entry.status] + 1 }),
    { absorbed: 0, partial: 0, todo: 0, retire: 0, removed: 0 } as Record<UiMigrationStatus, number>,
  );

  return (
    <div className="space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="border border-border bg-card px-6 py-6">
          <div className="flex items-center gap-3 text-sm font-medium text-primary">
            <Route className="h-4 w-4" />
            UI Migration
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground">기능 이동 기록</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
            이전 통합 화면의 기능을 포트폴리오, 종목분석, 전략, 관리 화면으로 나눈 내역입니다. 현재 사용자가
            실제로 접근하는 화면과 데이터/API 기준으로 정리했습니다.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label="전체 기능" value={uiMigrationEntries.length} icon={<Layers3 className="h-4 w-4" />} />
          <Metric label="이동 예정" value={counts.todo} icon={<Route className="h-4 w-4" />} />
          <Metric label="부분 흡수" value={counts.partial} icon={<Route className="h-4 w-4" />} />
          <Metric label="흡수됨" value={counts.absorbed} icon={<Layers3 className="h-4 w-4" />} />
          <Metric label="제거됨" value={counts.removed} icon={<Layers3 className="h-4 w-4" />} />
        </div>
      </section>

      <section className="overflow-x-auto border border-border bg-card">
        <div className="min-w-[1120px]">
          <div className="grid grid-cols-[0.9fr_1fr_1fr_1.2fr_0.7fr] border-b border-border bg-muted/30 px-4 py-3 text-xs font-semibold text-muted-foreground">
            <span>기능</span>
            <span>현재 위치</span>
            <span>데이터/API</span>
            <span>이동 위치/계획</span>
            <span>상태</span>
          </div>
          {uiMigrationEntries.map((entry) => (
            <article
              key={entry.feature}
              className="grid grid-cols-[0.9fr_1fr_1fr_1.2fr_0.7fr] gap-4 border-b border-border px-4 py-4 last:border-b-0"
            >
              <div>
                <h2 className="font-semibold text-foreground">{entry.feature}</h2>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {entry.currentCode.map((path) => (
                    <span key={path} className="bg-muted px-2 py-1 font-data text-[11px] text-muted-foreground">
                      {path}
                    </span>
                  ))}
                </div>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">{entry.legacySurface}</p>
              <p className="font-data text-xs leading-6 text-foreground">{entry.currentData}</p>
              <div>
                <p className="text-sm font-medium text-foreground">{entry.targetSurface}</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{entry.plan}</p>
              </div>
              <div>
                <span className={`inline-flex border px-2 py-1 text-xs font-medium ${statusClasses[entry.status]}`}>
                  {uiMigrationStatusLabels[entry.status]}
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
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
