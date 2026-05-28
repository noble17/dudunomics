import type { ComponentType } from "react";

export interface WidgetMeta {
  label: string;
  component: ComponentType;
  defaultW: number;
  defaultH: number;
}

// 위젯은 Task 10에서 등록됨
export const WIDGET_REGISTRY: Record<string, WidgetMeta> = {};
