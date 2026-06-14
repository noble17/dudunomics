"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Bell, Trash2 } from "lucide-react";
import { alertsApi } from "@/lib/api";
import type { AlertConditionType, AlertEvent, AlertIn, AlertTemplate, AlertTemplateItem } from "@/lib/types";
import { formatConditionMsg } from "@/hooks/useAlerts";

export const CONDITION_OPTIONS: { value: AlertConditionType; label: string; needsValue: boolean }[] = [
  { value: "price_above", label: "가격 초과", needsValue: true },
  { value: "price_below", label: "가격 미만", needsValue: true },
  { value: "rsi_above", label: "RSI 기준 상회", needsValue: true },
  { value: "rsi_below", label: "RSI 기준 하회", needsValue: true },
  { value: "ma_golden_cross", label: "골든크로스", needsValue: false },
  { value: "ma_dead_cross", label: "데드크로스", needsValue: false },
  { value: "ema20_near", label: "EMA20 근접", needsValue: true },
  { value: "ema50_near", label: "EMA50 근접", needsValue: true },
  { value: "ema200_near", label: "EMA200 근접", needsValue: true },
  { value: "price_cross_above_ema20", label: "주가 EMA20 상향돌파", needsValue: false },
  { value: "price_cross_above_ema50", label: "주가 EMA50 상향돌파", needsValue: false },
  { value: "price_cross_above_ema200", label: "주가 EMA200 상향돌파", needsValue: false },
  { value: "price_cross_below_ema20", label: "주가 EMA20 하향돌파", needsValue: false },
  { value: "price_cross_below_ema50", label: "주가 EMA50 하향돌파", needsValue: false },
  { value: "price_cross_below_ema200", label: "주가 EMA200 하향돌파", needsValue: false },
];

export function optionFor(type: AlertConditionType) {
  return CONDITION_OPTIONS.find((option) => option.value === type) ?? CONDITION_OPTIONS[0];
}

export function conditionLabel(item: AlertTemplateItem) {
  const option = optionFor(item.condition_type);
  return `${option.label}${item.condition_value != null ? ` ${item.condition_value}` : ""}`;
}

interface Props {
  ticker?: string;
  mode?: "ticker" | "manage";
}

export function AlertManager({ ticker, mode = "manage" }: Props) {
  const fixedTicker = ticker?.toUpperCase();
  const [inputTicker, setInputTicker] = useState(fixedTicker ?? "");
  const [conditionType, setConditionType] = useState<AlertConditionType>("price_above");
  const [conditionValue, setConditionValue] = useState("");
  const [saving, setSaving] = useState(false);
  const { data: conditions = [], mutate: mutateConditions } = useSWR("/api/alerts", alertsApi.list, { refreshInterval: 30_000 });
  const { data: templates = [] } = useSWR<AlertTemplate[]>("/api/alerts/templates", alertsApi.templates);
  const { data: events = [] } = useSWR<AlertEvent[]>("/api/alerts/events", alertsApi.events, { refreshInterval: 30_000 });

  const selectedOption = optionFor(conditionType);
  const visibleConditions = useMemo(
    () => fixedTicker ? conditions.filter((condition) => condition.ticker === fixedTicker) : conditions,
    [conditions, fixedTicker],
  );
  const visibleEvents = useMemo(
    () => fixedTicker ? events.filter((event) => event.ticker === fixedTicker) : events,
    [events, fixedTicker],
  );

  const addAlert = async () => {
    const targetTicker = (fixedTicker ?? inputTicker).trim().toUpperCase();
    if (!targetTicker) return;
    if (selectedOption.needsValue && (!conditionValue.trim() || Number.isNaN(parseFloat(conditionValue)))) return;

    const body: AlertIn = {
      ticker: targetTicker,
      condition_type: conditionType,
      condition_value: selectedOption.needsValue ? parseFloat(conditionValue) : null,
    };

    setSaving(true);
    try {
      await alertsApi.create(body);
      setConditionValue("");
      if (!fixedTicker) setInputTicker("");
      await mutateConditions();
    } finally {
      setSaving(false);
    }
  };

  const removeAlert = async (id: number) => {
    await alertsApi.delete(id);
    await mutateConditions();
  };

  const applyTemplate = async (template: AlertTemplate) => {
    const targetTicker = (fixedTicker ?? inputTicker).trim().toUpperCase();
    if (!targetTicker) return;

    const existingKeys = new Set(
      conditions
        .filter((condition) => condition.ticker === targetTicker)
        .map((condition) => `${condition.condition_type}:${condition.condition_value ?? ""}`),
    );
    const nextItems = template.items.filter(
      (item) => !existingKeys.has(`${item.condition_type}:${item.condition_value ?? ""}`),
    );
    if (!nextItems.length) return;

    setSaving(true);
    try {
      await Promise.all(nextItems.map((item) => alertsApi.create({ ticker: targetTicker, ...item })));
      if (!fixedTicker) setInputTicker("");
      await mutateConditions();
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Bell className="h-4 w-4 text-primary" />
        <div>
          <p className="text-sm font-semibold text-foreground">{mode === "ticker" ? "종목 알림" : "알림 관리"}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            가격, RSI, 이동평균 조건을 저장하면 백엔드 alert_check 작업이 주기적으로 확인합니다.
          </p>
        </div>
      </div>

      <div className="grid gap-5 p-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-3">
          <div className="space-y-2 rounded-lg border border-border bg-background/45 p-3">
            <div>
              <p className="text-xs font-medium text-foreground">템플릿 적용</p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                관리 탭에서 수정한 템플릿을 현재 종목에 한 번에 추가합니다.
              </p>
            </div>
            <div className="grid gap-2">
              {templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => applyTemplate(template)}
                  disabled={saving}
                  className="rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="block text-xs font-medium text-foreground">{template.name}</span>
                  <span className="mt-1 block line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                    {template.description || template.items.map(conditionLabel).join(" · ")}
                  </span>
                </button>
              ))}
              {!templates.length && (
                <p className="rounded border border-border px-3 py-6 text-center text-[11px] text-muted-foreground">
                  템플릿을 불러오는 중입니다.
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-2">
            {!fixedTicker && (
              <label className="grid gap-1 text-xs text-muted-foreground">
                티커
                <input
                  value={inputTicker}
                  onChange={(event) => setInputTicker(event.target.value.toUpperCase())}
                  placeholder="AAPL"
                  className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            )}
            <label className="grid gap-1 text-xs text-muted-foreground">
              조건
              <select
                value={conditionType}
                onChange={(event) => setConditionType(event.target.value as AlertConditionType)}
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              >
                {CONDITION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            {selectedOption.needsValue && (
              <label className="grid gap-1 text-xs text-muted-foreground">
                기준값{conditionType.includes("_near") ? " (% 이내)" : ""}
                <input
                  value={conditionValue}
                  onChange={(event) => setConditionValue(event.target.value)}
                  type="number"
                  placeholder={conditionType.includes("_near") ? "예: 1" : "값 입력"}
                  className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
                />
              </label>
            )}
          </div>
          <button
            type="button"
            onClick={addAlert}
            disabled={saving}
            className="inline-flex h-9 w-full items-center justify-center border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "저장 중" : "알림 추가"}
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">활성 조건</p>
            <div className="divide-y divide-border border border-border">
              {visibleConditions.length ? visibleConditions.map((condition) => (
                <div key={condition.id} className="flex items-center justify-between gap-3 px-3 py-2">
                  <div>
                    <p className="font-data text-sm text-foreground">{condition.ticker}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {optionFor(condition.condition_type).label}
                      {condition.condition_value != null ? ` ${condition.condition_value}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeAlert(condition.id)}
                    className="inline-flex h-8 w-8 items-center justify-center border border-border text-muted-foreground hover:border-loss hover:text-loss"
                    title="알림 삭제"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )) : (
                <div className="px-3 py-8 text-center text-xs text-muted-foreground">활성 조건이 없습니다.</div>
              )}
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">최근 발생</p>
            <div className="divide-y divide-border border border-border">
              {visibleEvents.length ? visibleEvents.slice(0, 12).map((event) => (
                <div key={event.id} className="px-3 py-2">
                  <p className="text-sm text-foreground">{formatConditionMsg(event)}</p>
                  <p className="mt-1 font-data text-xs text-muted-foreground">
                    {new Date(event.triggered_at).toLocaleString("ko-KR")}
                  </p>
                </div>
              )) : (
                <div className="px-3 py-8 text-center text-xs text-muted-foreground">발생 이력이 없습니다.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
