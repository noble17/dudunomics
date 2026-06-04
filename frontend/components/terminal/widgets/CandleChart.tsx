"use client";

import { TickerCandleChart } from "@/components/charts/ticker-candle-chart";

interface Props {
  ticker: string;
}

export function CandleChart({ ticker }: Props) {
  return <TickerCandleChart ticker={ticker} />;
}
