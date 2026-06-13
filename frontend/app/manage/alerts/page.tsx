import { AlertManager } from "@/components/alerts/alert-manager";

export default function ManageAlertsPage() {
  return (
    <div className="space-y-6">
      <header className="border border-border bg-card px-5 py-5">
        <p className="font-data text-[10px] tracking-[0.24em] text-primary">ALERT OPERATIONS</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">알림 관리</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          조건 추가/삭제와 최근 발생 이력을 확인합니다. 스케줄 작업에서 발생한 알림도 이 화면에서 함께 봅니다.
        </p>
      </header>
      <AlertManager mode="manage" />
    </div>
  );
}
