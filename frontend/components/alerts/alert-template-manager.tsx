"use client";

import { useState } from "react";
import useSWR from "swr";
import { CopyPlus, Trash2 } from "lucide-react";
import { alertsApi } from "@/lib/api";
import type { AlertConditionType, AlertTemplate, AlertTemplateIn, AlertTemplateItem } from "@/lib/types";
import { CONDITION_OPTIONS, conditionLabel, optionFor } from "./alert-manager";

function emptyForm(): AlertTemplateIn {
  return { name: "", description: "", items: [] };
}

export function AlertTemplateManager() {
  const { data: templates = [], mutate } = useSWR<AlertTemplate[]>("/api/alerts/templates", alertsApi.templates);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<AlertTemplateIn>(emptyForm());
  const [conditionType, setConditionType] = useState<AlertConditionType>("ema20_near");
  const [conditionValue, setConditionValue] = useState("2");
  const [saving, setSaving] = useState(false);

  const selectedOption = optionFor(conditionType);

  const startNew = () => {
    setEditingId(null);
    setForm(emptyForm());
    setConditionType("ema20_near");
    setConditionValue("2");
  };

  const startEdit = (template: AlertTemplate) => {
    setEditingId(template.id);
    setForm({
      name: template.name,
      description: template.description,
      items: template.items,
    });
    setConditionType(template.items[0]?.condition_type ?? "ema20_near");
    setConditionValue(String(template.items[0]?.condition_value ?? "2"));
  };

  const addItem = () => {
    if (selectedOption.needsValue && (!conditionValue.trim() || Number.isNaN(parseFloat(conditionValue)))) return;
    const item: AlertTemplateItem = {
      condition_type: conditionType,
      condition_value: selectedOption.needsValue ? parseFloat(conditionValue) : null,
    };
    const key = `${item.condition_type}:${item.condition_value ?? ""}`;
    if (form.items.some((existing) => `${existing.condition_type}:${existing.condition_value ?? ""}` === key)) return;
    setForm((current) => ({ ...current, items: [...current.items, item] }));
  };

  const removeItem = (index: number) => {
    setForm((current) => ({ ...current, items: current.items.filter((_, itemIndex) => itemIndex !== index) }));
  };

  const save = async () => {
    const name = form.name.trim();
    if (!name || !form.items.length) return;
    setSaving(true);
    try {
      const body = {
        name,
        description: form.description?.trim() || null,
        items: form.items,
      };
      if (editingId == null) {
        await alertsApi.createTemplate(body);
      } else {
        await alertsApi.updateTemplate(editingId, body);
      }
      startNew();
      await mutate();
    } finally {
      setSaving(false);
    }
  };

  const removeTemplate = async (id: number) => {
    await alertsApi.deleteTemplate(id);
    if (editingId === id) startNew();
    await mutate();
  };

  return (
    <section className="border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <CopyPlus className="h-4 w-4 text-primary" />
        <div>
          <p className="text-sm font-semibold text-foreground">템플릿 관리</p>
          <p className="mt-1 text-xs text-muted-foreground">
            기본 추천 템플릿도 내 기준에 맞게 수정할 수 있습니다. 저장된 템플릿은 종목 알림 모달에서 바로 적용됩니다.
          </p>
        </div>
      </div>

      <div className="grid gap-5 p-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid gap-3 md:grid-cols-2">
          {templates.map((template) => (
            <article key={template.id} className="rounded-lg border border-border bg-background/35 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-sm font-semibold text-foreground">{template.name}</h3>
                    {template.is_default && (
                      <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] text-primary">
                        기본
                      </span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {template.description || "설명 없음"}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => startEdit(template)}
                    className="rounded border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary"
                  >
                    수정
                  </button>
                  <button
                    type="button"
                    onClick={() => removeTemplate(template.id)}
                    className="inline-flex h-7 w-7 items-center justify-center rounded border border-border text-muted-foreground hover:border-loss/50 hover:text-loss"
                    title="템플릿 삭제"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {template.items.map((item, index) => (
                  <span key={`${template.id}-${index}`} className="rounded-full border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground">
                    {conditionLabel(item)}
                  </span>
                ))}
              </div>
            </article>
          ))}
          {!templates.length && (
            <div className="rounded-lg border border-border px-4 py-10 text-center text-xs text-muted-foreground">
              템플릿을 불러오는 중입니다.
            </div>
          )}
        </div>

        <aside className="rounded-lg border border-border bg-background/45 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">
                {editingId == null ? "새 템플릿" : "템플릿 수정"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">조건을 여러 개 담아 저장합니다.</p>
            </div>
            <button
              type="button"
              onClick={startNew}
              className="rounded border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary"
            >
              새로
            </button>
          </div>

          <div className="grid gap-2">
            <input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="템플릿 이름"
              className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
            />
            <input
              value={form.description ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="설명"
              className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
            />
            <div className="grid gap-2 sm:grid-cols-[1fr_96px]">
              <select
                value={conditionType}
                onChange={(event) => setConditionType(event.target.value as AlertConditionType)}
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              >
                {CONDITION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <input
                value={conditionValue}
                onChange={(event) => setConditionValue(event.target.value)}
                type="number"
                disabled={!selectedOption.needsValue}
                placeholder={selectedOption.needsValue ? "값" : "-"}
                className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary disabled:opacity-40"
              />
            </div>
            <button
              type="button"
              onClick={addItem}
              className="h-9 border border-border px-3 text-xs text-muted-foreground hover:border-primary/50 hover:text-primary"
            >
              조건 추가
            </button>

            <div className="min-h-16 rounded border border-border bg-card/60 p-2">
              {form.items.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {form.items.map((item, index) => (
                    <button
                      key={`${item.condition_type}-${item.condition_value ?? "none"}-${index}`}
                      type="button"
                      onClick={() => removeItem(index)}
                      className="rounded-full border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-loss/50 hover:text-loss"
                      title="클릭하면 조건을 제거합니다."
                    >
                      {conditionLabel(item)} ×
                    </button>
                  ))}
                </div>
              ) : (
                <p className="px-1 py-5 text-center text-[11px] text-muted-foreground">조건을 추가하세요.</p>
              )}
            </div>

            <button
              type="button"
              onClick={save}
              disabled={saving || !form.name.trim() || !form.items.length}
              className="inline-flex h-9 items-center justify-center border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "저장 중" : editingId == null ? "템플릿 저장" : "수정 저장"}
            </button>
          </div>
        </aside>
      </div>
    </section>
  );
}
