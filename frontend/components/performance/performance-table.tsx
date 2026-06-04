"use client";

import { useRef, useState, type MouseEvent } from "react";
import type { PortfolioAnalyticsRow, TickerPerformance, WatchlistItem } from "@/lib/types";

type Row = TickerPerformance | PortfolioAnalyticsRow | WatchlistItem;

interface Props {
  rows: Row[];
  mode: "portfolio" | "watchlist";
  onSelect?: (ticker: string) => void;
  onRemove?: (row: WatchlistItem) => void;
}

const HEAD = "whitespace-nowrap px-4 py-3 text-right font-normal text-[11px] font-medium text-muted-foreground";
const CELL = "whitespace-nowrap px-4 py-3 text-right font-data tabular-nums";
const STICKY_SYMBOL =
  "sticky left-0 z-20 w-[112px] min-w-[112px] bg-card px-4 py-3 text-left shadow-[1px_0_0_rgba(214,224,239,0.09)] group-hover:bg-secondary";

function fmtNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return "—";
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtCompact(value: number | null | undefined) {
  if (value == null) return "—";
  return Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function fmtPct(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function tone(value: number | null | undefined) {
  if (value == null) return "text-muted-foreground";
  return value >= 0 ? "text-gain" : "text-loss";
}

const TIMING_LABEL: Record<string, string> = {
  suitable: "적합",
  watch: "관망",
  unsuitable: "부적합",
  unknown: "부족",
};

const TIMING_TONE: Record<string, string> = {
  suitable: "border-rise/40 bg-rise/10 text-rise",
  watch: "border-primary/35 bg-primary/10 text-primary",
  unsuitable: "border-fall/40 bg-fall/10 text-fall",
  unknown: "border-border bg-muted/30 text-muted-foreground",
};

function MaCell({ label, ma, vs }: { label: string; ma: number | null; vs: number | null }) {
  return (
    <td className={`${CELL} min-w-[124px] border-t border-border ${tone(vs)}`}>
      <div className="inline-flex min-w-[92px] flex-col items-end rounded-lg border border-border/80 bg-background/55 px-2.5 py-1.5">
        <span className="text-[13px] leading-none">{fmtPct(vs)}</span>
        <span className="mt-1 text-[10px] leading-none text-muted-foreground">{label} {fmtNumber(ma)}</span>
      </div>
    </td>
  );
}

function rangePosition(price: number | null, low: number | null, high: number | null) {
  if (price == null || low == null || high == null || high <= low) return null;
  return Math.min(100, Math.max(0, ((price - low) / (high - low)) * 100));
}

function RangeCell({ price, low, high }: { price: number | null; low: number | null; high: number | null }) {
  const position = rangePosition(price, low, high);
  return (
    <td className={`${CELL} min-w-[132px] border-t border-border text-muted-foreground`}>
      <div className="inline-flex w-[116px] flex-col items-stretch gap-1.5">
        <div className="flex items-center justify-between gap-2 text-[10px] leading-none">
          <span className="text-muted-foreground/60">저</span>
          <span title={fmtNumber(low)}>{fmtNumber(low)}</span>
        </div>
        <span className="relative h-2 rounded-full border border-border bg-muted/50">
          <span className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-border" />
          {position != null && (
            <span
              className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-card"
              style={{ left: `${position}%` }}
            />
          )}
        </span>
        <div className="flex items-center justify-between gap-2 text-[10px] leading-none">
          <span className="text-muted-foreground/60">고</span>
          <span title={fmtNumber(high)}>{fmtNumber(high)}</span>
        </div>
      </div>
    </td>
  );
}

function GrowthCell({ value }: { value: number | null }) {
  const label = value == null ? "—" : value.toFixed(1);
  return (
    <td className={`${CELL} border-t border-border`}>
      <span className="inline-flex min-w-[54px] justify-center rounded-full border border-primary/25 bg-primary/10 px-2 py-1 text-xs text-primary">
        {label}
      </span>
    </td>
  );
}

function TimingCell({ row }: { row: WatchlistItem }) {
  const status = row.timing_status ?? "unknown";
  const details = [
    row.timing_aligned ? "정배열" : null,
    row.timing_pullback_stage && row.timing_pullback_stage !== "none" ? "눌림목" : null,
    row.timing_volume_level ? `거래량 ${row.timing_volume_level}` : null,
    row.timing_rsi_level ? `RSI ${row.timing_rsi_level}` : null,
  ].filter(Boolean);

  return (
    <td className={`${CELL} border-t border-border`}>
      <div className="inline-flex min-w-[92px] flex-col items-end gap-1">
        <span className={`rounded-full border px-2 py-1 text-[11px] ${TIMING_TONE[status] ?? TIMING_TONE.unknown}`}>
          {TIMING_LABEL[status] ?? status}
        </span>
        <span className="max-w-[110px] truncate text-[10px] text-muted-foreground" title={details.join(" · ")}>
          {details.length ? details.join(" · ") : "신호 없음"}
        </span>
      </div>
    </td>
  );
}

function isPortfolioRow(row: Row): row is PortfolioAnalyticsRow {
  return "quantity" in row;
}

function isWatchlistRow(row: Row): row is WatchlistItem {
  return "watchlist_id" in row;
}

export function PerformanceTable({ rows, mode, onSelect, onRemove }: Props) {
  const tableMinWidth = mode === "portfolio" ? 1960 : 1940;
  const scrollerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef({ active: false, startX: 0, scrollLeft: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const startDrag = (event: MouseEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("button")) return;
    const scroller = scrollerRef.current;
    if (!scroller) return;
    dragRef.current = {
      active: true,
      startX: event.clientX,
      scrollLeft: scroller.scrollLeft,
    };
    setIsDragging(true);
    event.preventDefault();
  };

  const moveDrag = (event: MouseEvent<HTMLDivElement>) => {
    const scroller = scrollerRef.current;
    if (!scroller || !dragRef.current.active) return;
    const delta = event.clientX - dragRef.current.startX;
    scroller.scrollLeft = dragRef.current.scrollLeft - delta;
  };

  const stopDrag = () => {
    dragRef.current.active = false;
    setIsDragging(false);
  };

  return (
    <div className="w-full min-w-0 max-w-full overflow-hidden rounded-b-xl border-t border-border bg-card">
      <div
        ref={scrollerRef}
        onMouseDown={startDrag}
        onMouseMove={moveDrag}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        className={`w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain ${isDragging ? "cursor-grabbing select-none" : "cursor-grab"}`}
      >
        <table className="w-full table-fixed border-separate border-spacing-0 text-sm" style={{ minWidth: tableMinWidth }}>
          <colgroup>
            <col className="w-[112px]" />
            <col className="w-[190px]" />
            {mode === "portfolio" && (
              <>
                <col className="w-[92px]" />
                <col className="w-[104px]" />
                <col className="w-[100px]" />
              </>
            )}
            <col className="w-[104px]" />
            <col className="w-[92px]" />
            <col className="w-[118px]" />
            <col className="w-[118px]" />
            <col className="w-[98px]" />
            <col className="w-[98px]" />
            <col className="w-[98px]" />
            <col className="w-[98px]" />
            <col className="w-[132px]" />
            <col className="w-[132px]" />
            <col className="w-[136px]" />
            <col className="w-[136px]" />
            <col className="w-[136px]" />
            {mode === "watchlist" && (
              <>
                <col className="w-[86px]" />
                <col className="w-[130px]" />
                <col className="w-[72px]" />
              </>
            )}
          </colgroup>
          <thead className="bg-card">
            <tr>
              {[
                "Symbol",
                "Name",
                ...(mode === "portfolio" ? ["보유", "평단", "수익률"] : []),
                "Price",
                "Change %",
                "Volume",
                "Avg Vol",
                "1W Perf",
                "1M Perf",
                "6M Perf",
                "YTD Perf",
                "Vs 20D MA",
                "Vs 50D MA",
                "Vs 200D MA",
                "Day Range",
                "52W Range",
                ...(mode === "watchlist" ? ["성장", "타이밍", ""] : []),
              ].map((header, index) => (
                <th
                  key={`${header}-${index}`}
                  className={index === 0 ? `${HEAD} ${STICKY_SYMBOL} z-30` : HEAD}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={isWatchlistRow(row) ? `${row.watchlist_id}-${row.ticker}-${row.universe}` : row.ticker}
                className="group"
              >
                <td className={`${STICKY_SYMBOL} border-t border-border`}>
                  <button
                    type="button"
                    onClick={() => onSelect?.(row.ticker)}
                    className="font-data text-[13px] font-medium text-primary tabular-nums hover:underline"
                  >
                    {row.ticker}
                  </button>
                </td>
                <td className="border-t border-border px-4 py-3 text-right text-muted-foreground">
                  <p className="line-clamp-2 max-w-[170px] leading-snug">{row.name}</p>
                </td>
                {mode === "portfolio" && isPortfolioRow(row) && (
                  <>
                    <td className={`${CELL} border-t border-border`}>{fmtNumber(row.quantity, 4)}</td>
                    <td className={`${CELL} border-t border-border text-muted-foreground`}>{fmtNumber(row.avg_price)}</td>
                    <td className={`${CELL} border-t border-border ${tone(row.return_pct)}`}>{fmtPct(row.return_pct)}</td>
                  </>
                )}
                <td className={`${CELL} border-t border-border text-foreground`}>{fmtNumber(row.price)}</td>
                <td className={`${CELL} border-t border-border ${tone(row.change_pct)}`}>{fmtPct(row.change_pct)}</td>
                <td className={`${CELL} border-t border-border`}>{fmtCompact(row.volume)}</td>
                <td className={`${CELL} border-t border-border text-muted-foreground`}>{fmtCompact(row.avg_volume20)}</td>
                <td className={`${CELL} border-t border-border ${tone(row.perf_1w)}`}>{fmtPct(row.perf_1w)}</td>
                <td className={`${CELL} border-t border-border ${tone(row.perf_1m)}`}>{fmtPct(row.perf_1m)}</td>
                <td className={`${CELL} border-t border-border ${tone(row.perf_6m)}`}>{fmtPct(row.perf_6m)}</td>
                <td className={`${CELL} border-t border-border ${tone(row.perf_ytd)}`}>{fmtPct(row.perf_ytd)}</td>
                <MaCell label="20D" ma={row.ma20} vs={row.price_vs_ma20} />
                <MaCell label="50D" ma={row.ma50} vs={row.price_vs_ma50} />
                <MaCell label="200D" ma={row.ma200} vs={row.price_vs_ma200} />
                <RangeCell price={row.price} low={row.day_low} high={row.day_high} />
                <RangeCell price={row.price} low={row.range_52w_low} high={row.range_52w_high} />
                {mode === "watchlist" && isWatchlistRow(row) && (
                  <>
                    <GrowthCell value={row.growth_composite} />
                    <TimingCell row={row} />
                    <td className="border-t border-border px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => onRemove?.(row)}
                        className="rounded-full border border-border px-2 py-1 text-[11px] text-muted-foreground hover:border-fall/40 hover:text-fall"
                      >
                        제거
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
