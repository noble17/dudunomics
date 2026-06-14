"use client";

import { useState } from "react";
import { AlertManager } from "@/components/alerts/alert-manager";
import { AlertTemplateManager } from "@/components/alerts/alert-template-manager";

type Tab = "conditions" | "templates";

const tabs: { id: Tab; label: string; description: string }[] = [
  { id: "conditions", label: "조건 알림", description: "종목별 활성 조건과 최근 발생 이력을 확인합니다." },
  { id: "templates", label: "템플릿 관리", description: "추천 템플릿과 내 템플릿을 수정하고 DB에 저장합니다." },
];

export default function ManageAlertsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("conditions");

  return (
    <div className="space-y-6">
      <header className="border border-border bg-card px-5 py-5">
        <p className="font-data text-[10px] tracking-[0.24em] text-primary">ALERT OPERATIONS</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">알림 관리</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          조건 알림과 템플릿을 관리합니다. 템플릿은 DB에 저장되어 종목 알림 모달에서 바로 적용됩니다.
        </p>
      </header>

      <section className="border border-border bg-card p-2">
        <div className="grid gap-2 md:grid-cols-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                activeTab === tab.id
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
              }`}
            >
              <span className="block text-sm font-semibold">{tab.label}</span>
              <span className="mt-1 block text-xs">{tab.description}</span>
            </button>
          ))}
        </div>
      </section>

      {activeTab === "conditions" ? <AlertManager mode="manage" /> : <AlertTemplateManager />}
    </div>
  );
}
