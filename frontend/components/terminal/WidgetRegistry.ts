import type { ComponentType } from "react";
import { PortfolioWidget } from "./widgets/Portfolio";
import { WatchlistWidget } from "./widgets/Watchlist";
import { ScreenerWidget } from "./widgets/Screener";
import { BacktestWidget } from "./widgets/Backtest";

export interface WidgetMeta {
  label: string;
  component: ComponentType;
  defaultW: number;
  defaultH: number;
}

export const WIDGET_REGISTRY: Record<string, WidgetMeta> = {
  portfolio: { label: "포트폴리오", component: PortfolioWidget, defaultW: 12, defaultH: 10 },
  watchlist: { label: "워치리스트", component: WatchlistWidget, defaultW: 6, defaultH: 8 },
  screener:  { label: "종목분석",   component: ScreenerWidget,  defaultW: 6, defaultH: 8 },
  backtest:  { label: "백테스트",   component: BacktestWidget,  defaultW: 6, defaultH: 6 },
};
