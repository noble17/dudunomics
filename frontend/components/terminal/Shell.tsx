"use client";
import { useEffect, useRef, useState } from "react";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { GridLayout, useContainerWidth } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import { useWorkspaceStore } from "@/lib/stores/workspace";
import { WidgetFrame } from "./WidgetFrame";
import { WIDGET_REGISTRY } from "./WidgetRegistry";
import { WatchlistWidget } from "./widgets/Watchlist";
import type { WidgetItem } from "@/lib/types";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

function CenterGrid() {
  const { layout, updateGrid, removeWidget } = useWorkspaceStore();
  const { width, containerRef } = useContainerWidth({ initialWidth: 800 });
  const widgets = layout.center_widgets ?? [];

  const rglLayout: Layout = widgets.map(w => ({
    i: w.i, x: w.x, y: w.y, w: w.w, h: w.h,
  }));

  function onLayoutChange(newLayout: Layout) {
    const updated: WidgetItem[] = widgets.map(w => {
      const l = newLayout.find((n: LayoutItem) => n.i === w.i);
      return l ? { ...w, x: l.x, y: l.y, w: l.w, h: l.h } : w;
    });
    updateGrid(updated);
  }

  return (
    <div ref={containerRef} className="h-full overflow-auto">
      <GridLayout
        layout={rglLayout}
        width={width}
        gridConfig={{ cols: 12, rowHeight: 40, margin: [4, 4], containerPadding: [4, 4] }}
        dragConfig={{ handle: ".widget-drag-handle" }}
        resizeConfig={{ handles: ["se"] }}
        onLayoutChange={onLayoutChange}
      >
        {widgets.map(w => {
          const meta = WIDGET_REGISTRY[w.type];
          if (!meta) return null;
          const Comp = meta.component;
          return (
            <div key={w.i}>
              <WidgetFrame
                title={meta.label}
                onClose={() => removeWidget(w.i)}
                className="h-full"
              >
                <Comp />
              </WidgetFrame>
            </div>
          );
        })}
      </GridLayout>
    </div>
  );
}

export function Shell() {
  const { loadWorkspace, loaded, layout } = useWorkspaceStore();

  useEffect(() => {
    if (!loaded) loadWorkspace();
  }, [loaded, loadWorkspace]);

  const panels = layout.panels ?? [22, 53, 25];

  return (
    <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
      <Panel defaultSize={panels[0]} minSize={12} className="flex flex-col">
        <div className="px-2 py-1 text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider border-b border-[var(--color-border)]">
          워치리스트
        </div>
        <div className="flex-1 overflow-auto p-2">
          <WatchlistWidget />
        </div>
      </Panel>

      <ResizeHandle />

      <Panel defaultSize={panels[1]} minSize={30} className="flex flex-col overflow-hidden">
        <CenterGrid />
      </Panel>

      <ResizeHandle />

      <Panel defaultSize={panels[2]} minSize={12} className="flex flex-col">
        <div className="px-2 py-1 text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider border-b border-[var(--color-border)]">
          AI / 뉴스 (M4~M5)
        </div>
        <div className="flex-1 overflow-auto p-2 text-xs text-[var(--color-text-secondary)]">
          M4에서 뉴스+번역, M5에서 AI 어시스턴트 연결 예정
        </div>
      </Panel>
    </PanelGroup>
  );
}
