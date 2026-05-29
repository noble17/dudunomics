"use client";
import { create } from "zustand";
import type { WidgetItem, WorkspaceLayout } from "@/lib/types";
import { workspaceApi } from "@/lib/api";

let _saveTimer: ReturnType<typeof setTimeout> | null = null;

interface WorkspaceState {
  layout: WorkspaceLayout;
  loaded: boolean;
  loadWorkspace: () => Promise<void>;
  addWidget: (type: string) => void;
  removeWidget: (id: string) => void;
  updateGrid: (items: WidgetItem[]) => void;
  setPanels: (panels: [number, number, number]) => void;
  _scheduleSave: () => void;
}

let _widgetCounter = 0;
function nextId() {
  return `w${++_widgetCounter}`;
}

const DEFAULT_LAYOUT: WorkspaceLayout = {
  panels: [22, 53, 25],
  center_widgets: [
    { i: "w1", type: "portfolio", x: 0, y: 0, w: 12, h: 8 },
    { i: "w2", type: "watchlist", x: 0, y: 8, w: 6, h: 6 },
    { i: "w3", type: "screener", x: 6, y: 8, w: 6, h: 6 },
  ],
  left_widget: "watchlist",
  right_widget: null,
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  layout: DEFAULT_LAYOUT,
  loaded: false,

  loadWorkspace: async () => {
    try {
      const res = await workspaceApi.get();
      const incoming = res.layout;
      const finalLayout = Object.keys(incoming).length > 0 ? incoming : DEFAULT_LAYOUT;
      // 기존 위젯 ID에서 최대 번호 추출해 _widgetCounter 동기화 (중복 키 방지)
      const maxN = (finalLayout.center_widgets ?? []).reduce((m, w) => {
        const n = parseInt(w.i.replace(/\D/g, ""), 10);
        return isNaN(n) ? m : Math.max(m, n);
      }, 0);
      if (maxN > _widgetCounter) _widgetCounter = maxN;
      set({ layout: finalLayout, loaded: true });
    } catch {
      set({ loaded: true });
    }
  },

  addWidget: (type: string) => {
    const { layout, _scheduleSave } = get();
    const existing = layout.center_widgets ?? [];
    const maxY = existing.reduce((m, w) => Math.max(m, w.y + w.h), 0);
    const item: WidgetItem = { i: nextId(), type, x: 0, y: maxY, w: 6, h: 6 };
    set({ layout: { ...layout, center_widgets: [...existing, item] } });
    _scheduleSave();
  },

  removeWidget: (id: string) => {
    const { layout, _scheduleSave } = get();
    set({
      layout: {
        ...layout,
        center_widgets: (layout.center_widgets ?? []).filter(w => w.i !== id),
      },
    });
    _scheduleSave();
  },

  updateGrid: (items: WidgetItem[]) => {
    const { layout, _scheduleSave } = get();
    set({ layout: { ...layout, center_widgets: items } });
    _scheduleSave();
  },

  setPanels: (panels) => {
    const { layout, _scheduleSave } = get();
    set({ layout: { ...layout, panels } });
    _scheduleSave();
  },

  _scheduleSave: () => {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => {
      workspaceApi.save(get().layout).catch(() => {});
    }, 800);
  },
}));
