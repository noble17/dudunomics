import Link from "next/link";
import { Activity, Bell, Database, Route, ServerCog, TrendingUp } from "lucide-react";

const manageItems = [
  {
    href: "/data-sources",
    title: "데이터 출처",
    description: "Provider별 역할, Primary/Fallback 정책, Toss 적용 범위를 확인합니다.",
    icon: Database,
  },
  {
    href: "/jobs",
    title: "작업관리",
    description: "스케줄 작업 상태와 최근 실행 이력을 확인하고 수동 실행합니다.",
    icon: Activity,
  },
  {
    href: "/manage/alerts",
    title: "알림 관리",
    description: "가격, RSI, 이동평균 알림 조건과 최근 발생 이력을 확인합니다.",
    icon: Bell,
  },
  {
    href: "/manage/ema-crosses",
    title: "EMA 골든크로스",
    description: "코스피, 코스닥, 미장 EMA 골든크로스 현재 상태와 상태 변경 이력을 확인합니다.",
    icon: TrendingUp,
  },
  {
    href: "/manage/migration",
    title: "기능 이동 기록",
    description: "이전 통합 화면의 기능이 포트폴리오, 종목분석, 전략, 관리로 나뉜 내역을 확인합니다.",
    icon: Route,
  },
];

export default function ManagePage() {
  return (
    <div className="space-y-6">
      <header className="border border-border bg-card px-5 py-5">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <ServerCog className="h-4 w-4" />
          Operations
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground">관리</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          데이터 출처, 작업 실행, 초기 적재, 연동 상태를 이 영역으로 모읍니다. 지금은 데이터 출처와 작업관리부터 연결합니다.
        </p>
      </header>

      <section className="grid gap-3 md:grid-cols-2">
        {manageItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className="group border border-border bg-card p-5 transition-colors hover:border-primary/60"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-foreground">{item.title}</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.description}</p>
                </div>
                <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-border bg-background text-primary transition-colors group-hover:border-primary">
                  <Icon className="h-4 w-4" />
                </span>
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
