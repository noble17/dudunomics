"use client";
import { useEffect } from "react";
import { Command } from "cmdk";
import { useCommandStore } from "@/lib/stores/command";
import { useWorkspaceStore } from "@/lib/stores/workspace";
import { WIDGET_REGISTRY } from "./WidgetRegistry";

export function CommandPalette() {
  const { open, closePalette } = useCommandStore();
  const addWidget = useWorkspaceStore(s => s.addWidget);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        useCommandStore.getState().openPalette();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[20vh] bg-black/40"
      onClick={closePalette}
    >
      <div
        className="w-full max-w-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-sm overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <Command className="[&_[cmdk-input]]:w-full [&_[cmdk-input]]:px-4 [&_[cmdk-input]]:py-3 [&_[cmdk-input]]:text-sm [&_[cmdk-input]]:bg-transparent [&_[cmdk-input]]:outline-none [&_[cmdk-input]]:border-b [&_[cmdk-input]]:border-[var(--color-border)] [&_[cmdk-input]]:text-[var(--color-text-primary)]">
          <Command.Input placeholder="위젯 추가, 페이지 이동…" />
          <Command.List className="max-h-64 overflow-auto p-2">
            <Command.Empty className="text-xs text-[var(--color-text-secondary)] px-3 py-4">
              결과 없음
            </Command.Empty>
            <Command.Group heading={<span className="text-[12px] text-[var(--color-text-secondary)] uppercase tracking-wider px-2">위젯 추가</span>}>
              {Object.entries(WIDGET_REGISTRY).map(([type, meta]) => (
                <Command.Item
                  key={type}
                  value={`위젯 ${meta.label} ${type}`}
                  onSelect={() => { addWidget(type); closePalette(); }}
                  className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer text-[var(--color-text-primary)] data-[selected=true]:bg-[var(--color-bg-primary)]"
                >
                  <span>{meta.label} 추가</span>
                  <span className="ml-auto text-[12px] text-[var(--color-text-secondary)] font-data">{type}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
