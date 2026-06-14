"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Bell, Trash2 } from "lucide-react";
import { alertsApi } from "@/lib/api";
import type { AlertConditionType, AlertEvent, AlertIn } from "@/lib/types";
import { formatConditionMsg } from "@/hooks/useAlerts";

const CONDITION_OPTIONS: { value: AlertConditionType; label: string; needsValue: boolean }[] = [
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

type AlertTemplateItem = Omit<AlertIn, "ticker">;
type AlertTemplate = {
  id: string;
  name: string;
  description: string;
  items: AlertTemplateItem[];
};

const CUSTOM_TEMPLATE_KEY = "dudunomics.alertTemplates.v1";

const ALERT_TEMPLATES: AlertTemplate[] = [
  {
    id: "trend-entry",
    name: "추세 진입 기본",
    description: "EMA20 근처 눌림과 재돌파를 같이 봅니다.",
    items: [
      { condition_type: "ema20_near", condition_value: 2 },
      { condition_type: "price_cross_above_ema20", condition_value: null },
      { condition_type: "price_cross_below_ema50", condition_value: null },
    ],
  },
  {
    id: "patient-pullback",
    name: "느긋한 눌림",
    description: "EMA50까지 기다리는 보수적인 감시입니다.",
    items: [
      { condition_type: "ema50_near", condition_value: 3 },
      { condition_type: "price_cross_above_ema50", condition_value: null },
      { condition_type: "price_cross_below_ema50", condition_value: null },
    ],
  },
  {
    id: "risk-guard",
    name: "보유 리스크",
    description: "중장기 추세 훼손을 빠르게 확인합니다.",
    items: [
      { condition_type: "price_cross_below_ema50", condition_value: null },
      { condition_type: "price_cross_below_ema200", condition_value: null },
    ],
  },
];

function optionFor(type: AlertConditionType) {
  return CONDITION_OPTIONS.find((option) => option.value === type) ?? CONDITION_OPTIONS[0];
}

function conditionLabel(item: AlertTemplateItem) {
  const option = optionFor(item.condition_type);
  return `${option.label}${item.condition_value != null ? ` ${item.condition_value}` : ""}`;
}

function loadCustomTemplates(): AlertTemplate[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(CUSTOM_TEMPLATE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((template) => (
      typeof template?.id === "string" &&
      typeof template?.name === "string" &&
      Array.isArray(template?.items)
    ));
  } catch {
    return [];
  }
}

function storeCustomTemplates(templates: AlertTemplate[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CUSTOM_TEMPLATE_KEY, JSON.stringify(templates));
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
  const [customTemplates, setCustomTemplates] = useState<AlertTemplate[]>([]);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [templateDescription, setTemplateDescription] = useState("");
  const [templateItems, setTemplateItems] = useState<AlertTemplateItem[]>([]);
  const [templateConditionType, setTemplateConditionType] = useState<AlertConditionType>("ema20_near");
  const [templateConditionValue, setTemplateConditionValue] = useState("2");
  const [saving, setSaving] = useState(false);
  const { data: conditions = [], mutate: mutateConditions } = useSWR("/api/alerts", alertsApi.list, { refreshInterval: 30_000 });
  const { data: events = [] } = useSWR<AlertEvent[]>("/api/alerts/events", alertsApi.events, { refreshInterval: 30_000 });

  const selectedOption = CONDITION_OPTIONS.find((option) => option.value === conditionType) ?? CONDITION_OPTIONS[0];
  const selectedTemplateOption = optionFor(templateConditionType);
  const visibleConditions = useMemo(
    () => fixedTicker ? conditions.filter((condition) => condition.ticker === fixedTicker) : conditions,
    [conditions, fixedTicker],
  );
  const visibleEvents = useMemo(
    () => fixedTicker ? events.filter((event) => event.ticker === fixedTicker) : events,
    [events, fixedTicker],
  );

  useEffect(() => {
    setCustomTemplates(loadCustomTemplates());
  }, []);

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

  const applyTemplate = async (template: typeof ALERT_TEMPLATES[number]) => {
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

  const persistTemplates = (nextTemplates: AlertTemplate[]) => {
    setCustomTemplates(nextTemplates);
    storeCustomTemplates(nextTemplates);
  };

  const startNewTemplate = () => {
    setEditingTemplateId(null);
    setTemplateName("");
    setTemplateDescription("");
    setTemplateItems([]);
    setTemplateConditionType("ema20_near");
    setTemplateConditionValue("2");
  };

  const startEditTemplate = (template: AlertTemplate) => {
    setEditingTemplateId(template.id);
    setTemplateName(template.name);
    setTemplateDescription(template.description);
    setTemplateItems(template.items);
    setTemplateConditionType(template.items[0]?.condition_type ?? "ema20_near");
    setTemplateConditionValue(String(template.items[0]?.condition_value ?? "2"));
  };

  const addTemplateItem = () => {
    if (selectedTemplateOption.needsValue && (!templateConditionValue.trim() || Number.isNaN(parseFloat(templateConditionValue)))) return;
    const item = {
      condition_type: templateConditionType,
      condition_value: selectedTemplateOption.needsValue ? parseFloat(templateConditionValue) : null,
    };
    setTemplateItems((current) => {
      const key = `${item.condition_type}:${item.condition_value ?? ""}`;
      if (current.some((existing) => `${existing.condition_type}:${existing.condition_value ?? ""}` === key)) return current;
      return [...current, item];
    });
  };

  const removeTemplateItem = (index: number) => {
    setTemplateItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const saveTemplate = () => {
    const name = templateName.trim();
    if (!name || !templateItems.length) return;
    const template: AlertTemplate = {
      id: editingTemplateId ?? `custom-${Date.now()}`,
      name,
      description: templateDescription.trim(),
      items: templateItems,
    };
    const nextTemplates = editingTemplateId
      ? customTemplates.map((item) => item.id === editingTemplateId ? template : item)
      : [...customTemplates, template];
    persistTemplates(nextTemplates);
    startNewTemplate();
  };

  const deleteTemplate = (templateId: string) => {
    persistTemplates(customTemplates.filter((template) => template.id !== templateId));
    if (editingTemplateId === templateId) startNewTemplate();
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
              <p className="text-xs font-medium text-foreground">기본 템플릿</p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                자주 쓰는 조건 묶음을 현재 종목에 한 번에 추가합니다.
              </p>
            </div>
            <div className="grid gap-2">
              {ALERT_TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => applyTemplate(template)}
                  disabled={saving}
                  className="rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="block text-xs font-medium text-foreground">{template.name}</span>
                  <span className="mt-1 block text-[11px] leading-snug text-muted-foreground">{template.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3 rounded-lg border border-border bg-background/45 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-foreground">내 템플릿</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  직접 만든 조건 묶음을 저장하고 다시 적용합니다.
                </p>
              </div>
              <button
                type="button"
                onClick={startNewTemplate}
                className="shrink-0 rounded border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary"
              >
                새로
              </button>
            </div>

            {customTemplates.length > 0 && (
              <div className="grid gap-2">
                {customTemplates.map((template) => (
                  <div key={template.id} className="rounded-lg border border-border px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => applyTemplate(template)}
                        disabled={saving}
                        className="min-w-0 flex-1 text-left disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <span className="block truncate text-xs font-medium text-foreground">{template.name}</span>
                        <span className="mt-1 block line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                          {template.description || template.items.map(conditionLabel).join(" · ")}
                        </span>
                      </button>
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => startEditTemplate(template)}
                          className="rounded border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary"
                        >
                          수정
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteTemplate(template.id)}
                          className="rounded border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-loss/50 hover:text-loss"
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="grid gap-2 border-t border-border pt-3">
              <input
                value={templateName}
                onChange={(event) => setTemplateName(event.target.value)}
                placeholder="템플릿 이름"
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
              <input
                value={templateDescription}
                onChange={(event) => setTemplateDescription(event.target.value)}
                placeholder="설명"
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              />
              <div className="grid gap-2 sm:grid-cols-[1fr_96px_auto]">
                <select
                  value={templateConditionType}
                  onChange={(event) => setTemplateConditionType(event.target.value as AlertConditionType)}
                  className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
                >
                  {CONDITION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <input
                  value={templateConditionValue}
                  onChange={(event) => setTemplateConditionValue(event.target.value)}
                  type="number"
                  disabled={!selectedTemplateOption.needsValue}
                  placeholder={selectedTemplateOption.needsValue ? "값" : "-"}
                  className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary disabled:opacity-40"
                />
                <button
                  type="button"
                  onClick={addTemplateItem}
                  className="h-9 border border-border px-3 text-xs text-muted-foreground hover:border-primary/50 hover:text-primary"
                >
                  조건 추가
                </button>
              </div>
              <div className="min-h-10 rounded border border-border bg-card/60 p-2">
                {templateItems.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {templateItems.map((item, index) => (
                      <button
                        key={`${item.condition_type}-${item.condition_value ?? "none"}-${index}`}
                        type="button"
                        onClick={() => removeTemplateItem(index)}
                        className="rounded-full border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-loss/50 hover:text-loss"
                        title="클릭하면 조건을 제거합니다."
                      >
                        {conditionLabel(item)} ×
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="px-1 py-2 text-[11px] text-muted-foreground">템플릿에 담을 조건을 추가하세요.</p>
                )}
              </div>
              <button
                type="button"
                onClick={saveTemplate}
                disabled={!templateName.trim() || !templateItems.length}
                className="inline-flex h-9 items-center justify-center border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {editingTemplateId ? "템플릿 수정 저장" : "내 템플릿 저장"}
              </button>
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
                      {CONDITION_OPTIONS.find((option) => option.value === condition.condition_type)?.label}
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
