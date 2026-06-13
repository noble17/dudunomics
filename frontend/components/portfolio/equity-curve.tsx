"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ComposedChart,
} from "recharts";
import { portfolioApi } from "@/lib/api";
import type { EventOut, PortfolioSnapshot, SnapshotHistory } from "@/lib/types";

interface Props {
  snapshot: PortfolioSnapshot;
  history: SnapshotHistory[];
}

type FlowMode = "10m" | "1h" | "1d" | "1w" | "1mo";

const FLOW_MODES: Array<{ key: FlowMode; label: string }> = [
  { key: "10m", label: "10분" },
  { key: "1h", label: "1시간" },
  { key: "1d", label: "일" },
  { key: "1w", label: "주" },
  { key: "1mo", label: "월" },
];

const FLOW_LIMIT: Record<FlowMode, number> = {
  "10m": 144,
  "1h": 168,
  "1d": 90,
  "1w": 104,
  "1mo": 36,
};
const CHART_MARGIN = { top: 18, right: 18, bottom: 4, left: 2 };
const AXIS_WIDTH = 58;

const EVENT_LABEL: Record<string, string> = { "입금": "IN", "출금": "OUT", "기타": "EVT" };
const EMPTY_FORM = { ts: "", label: "", amount: "", type: "입금" };

function won(value: number, digits = 0) {
  return `₩${Math.abs(value).toLocaleString("ko-KR", { maximumFractionDigits: digits })}`;
}

function signedWon(value: number) {
  return `${value >= 0 ? "+" : "-"}${won(value)}`;
}

function pct(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function compactWon(value: number) {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : value > 0 ? "+" : "";
  if (abs >= 100_000_000) return `${sign}₩${(abs / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${sign}₩${(abs / 10_000).toFixed(0)}만`;
  return `${sign}₩${abs.toLocaleString("ko-KR")}`;
}

function displayLabel(ts: string, mode: FlowMode) {
  const d = new Date(ts);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hour = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  if (mode === "10m") return `${hour}:${min}`;
  if (mode === "1h") return `${m}.${day} ${hour}시`;
  if (mode === "1d") return `${m}.${day}`;
  if (mode === "1w") return `${m}.${day}주`;
  return `${String(y).slice(2)}.${m}`;
}

function buildFlow(rows: SnapshotHistory[], mode: FlowMode) {
  const sorted = [...rows].sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  let previousTotal: number | null = null;
  return sorted.map((row) => {
    const start = previousTotal ?? row.total_with_cash_krw;
    const flow = row.total_with_cash_krw - start;
    previousTotal = row.total_with_cash_krw;
    return {
      key: row.ts,
      label: displayLabel(row.ts, mode),
      total: row.total_with_cash_krw,
      equity: row.total_equity_krw,
      cash: row.cash_krw,
      flow,
    };
  });
}

function flowSummary(data: ReturnType<typeof buildFlow>) {
  if (!data.length) return null;
  const first = data[0];
  const last = data[data.length - 1];
  const change = last.total - first.total;
  const changePct = first.total > 0 ? (change / first.total) * 100 : 0;
  return {
    current: last.total,
    equity: last.equity,
    cash: last.cash,
    change,
    changePct,
    high: Math.max(...data.map((d) => d.total)),
    low: Math.min(...data.map((d) => d.total)),
  };
}

function AssetMetric({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  const color = tone === "up" ? "text-gain" : tone === "down" ? "text-loss" : "text-foreground";
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`font-data text-sm font-medium ${color}`}>{value}</span>
    </div>
  );
}

function ChartTooltip({
  active,
  label,
  payload,
}: {
  active?: boolean;
  label?: string;
  payload?: Array<{ dataKey?: string; value?: number }>;
}) {
  if (!active || !payload?.length) return null;
  const row = Object.fromEntries(payload.map((item) => [item.dataKey, Number(item.value ?? 0)]));
  return (
    <div className="min-w-[220px] border border-border bg-popover px-4 py-3 text-popover-foreground">
      <p className="font-data text-sm text-foreground">{label}</p>
      <div className="mt-2 grid gap-1 font-data text-sm">
        <p className="flex items-center justify-between gap-4 text-[var(--portfolio-equity)]">
          <span>주식평가액</span>
          <span>{compactWon(row.equity ?? 0)}</span>
        </p>
        <p className="flex items-center justify-between gap-4 text-[var(--portfolio-total)]">
          <span>전체자산</span>
          <span>{compactWon(row.total ?? 0)}</span>
        </p>
        <p className={`flex items-center justify-between gap-4 ${(row.flow ?? 0) >= 0 ? "text-rise" : "text-fall"}`}>
          <span>기간 손익</span>
          <span>{compactWon(row.flow ?? 0)}</span>
        </p>
      </div>
    </div>
  );
}

function AssetFlowChart({ data }: { data: ReturnType<typeof buildFlow> }) {
  return (
    <div className="h-[420px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={CHART_MARGIN} barCategoryGap="45%">
          <defs>
            <linearGradient id="assetTotalFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--portfolio-total-fill)" stopOpacity={1} />
              <stop offset="64%" stopColor="var(--portfolio-total-fill)" stopOpacity={0.5} />
              <stop offset="100%" stopColor="var(--portfolio-total-fill)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={false}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            height={24}
          />
          <YAxis
            yAxisId="asset"
            tickFormatter={(value) => `${Math.round(Number(value) / 1_000_000)}M`}
            tick={{ fill: "var(--portfolio-total)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={AXIS_WIDTH}
            label={{
              value: "자산(원)",
              angle: -90,
              position: "insideLeft",
              fill: "var(--portfolio-total)",
              fontSize: 11,
              offset: 4,
            }}
          />
          <YAxis
            yAxisId="flow"
            orientation="right"
            tickFormatter={(value) => `${Math.round(Number(value) / 10_000)}만`}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={AXIS_WIDTH}
            label={{
              value: "기간손익",
              angle: 90,
              position: "insideRight",
              fill: "var(--muted-foreground)",
              fontSize: 11,
              offset: 4,
            }}
          />
          <Tooltip
            cursor={{ stroke: "var(--foreground)", strokeOpacity: 0.45, fill: "transparent" }}
            content={<ChartTooltip />}
          />
          <ReferenceLine yAxisId="flow" y={0} stroke="var(--border)" />
          <Bar
            yAxisId="flow"
            dataKey="flow"
            barSize={18}
            radius={[2, 2, 0, 0]}
          >
            {data.map((entry) => (
              <Cell key={entry.key} fill={entry.flow >= 0 ? "var(--rise)" : "var(--fall)"} />
            ))}
          </Bar>
          <Area
            yAxisId="asset"
            type="monotone"
            dataKey="total"
            stroke="var(--portfolio-total)"
            strokeWidth={2.5}
            fill="url(#assetTotalFill)"
            dot={{ r: 2.5, strokeWidth: 1 }}
          />
          <Area
            yAxisId="asset"
            type="monotone"
            dataKey="equity"
            stroke="var(--portfolio-equity)"
            strokeWidth={1.7}
            fill="transparent"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EquityCurve({ snapshot, history }: Props) {
  const [mode, setMode] = useState<FlowMode>("1d");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const { data: events = [], mutate: mutateEvents } =
    useSWR("/api/portfolio/events", portfolioApi.events);
  const { data: bucketHistory = history } =
    useSWR(`/api/portfolio/history?bucket=${mode}&limit=${FLOW_LIMIT[mode]}`, () => portfolioApi.history(mode, FLOW_LIMIT[mode]), {
      refreshInterval: 60_000,
    });

  const data = useMemo(() => buildFlow(bucketHistory, mode), [bucketHistory, mode]);
  const summary = flowSummary(data);
  const latest = summary ?? {
    current: snapshot.total_with_cash_krw,
    equity: snapshot.total_equity_krw,
    cash: snapshot.cash_krw,
    change: 0,
    changePct: 0,
    high: snapshot.total_with_cash_krw,
    low: snapshot.total_with_cash_krw,
  };

  const handleSave = async () => {
    if (!form.ts || !form.label) return;
    setSaving(true);
    try {
      await portfolioApi.addEvent({
        ts: form.ts,
        label: form.label,
        amount: parseInt(form.amount || "0", 10),
        type: form.type,
      });
      setForm(EMPTY_FORM);
      setShowForm(false);
      mutateEvents();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    await portfolioApi.deleteEvent(id);
    mutateEvents();
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="relative border border-border bg-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground">전체자산</p>
              <p className="mt-2 font-data text-3xl font-semibold tracking-tight text-foreground">
                {won(latest.current)}
              </p>
              <p className={`mt-2 font-data text-sm ${latest.change >= 0 ? "text-gain" : "text-loss"}`}>
                선택 구간 이익/손실 {signedWon(latest.change)} ({pct(latest.changePct)})
              </p>
            </div>
            <div className="flex rounded-full bg-muted p-1">
              {FLOW_MODES.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setMode(item.key)}
                  className={`h-8 min-w-12 rounded-full px-4 text-sm transition-colors ${
                    mode === item.key
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-background hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5 border-t border-border pt-4">
            {data.length > 1 ? (
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                  <span>자산 / 기간별 이익·손실</span>
                  <span className="font-data text-[var(--portfolio-total)]">왼쪽 축: 전체자산·주식평가액</span>
                  <span className="font-data">오른쪽 축: 기간손익 막대</span>
                </div>
                <AssetFlowChart data={data} />
              </div>
            ) : (
              <div className="flex h-[340px] items-center justify-center text-sm text-muted-foreground">
                자산 흐름을 그리려면 스냅샷이 2개 이상 필요합니다.
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-4 font-data text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 bg-[var(--portfolio-total)]" />전체자산</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 bg-[var(--portfolio-equity)]" />주식평가액</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 bg-rise" />이익</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-4 bg-fall" />손실</span>
          </div>
        </div>

        <div className="border border-border bg-card p-5">
          <p className="text-[11px] font-medium text-muted-foreground">자산 구성</p>
          <div className="mt-4">
            <AssetMetric label="보유상품 평가금액" value={won(latest.equity)} />
            <AssetMetric
              label="선택 구간 이익/손실"
              value={`${signedWon(latest.change)} (${pct(latest.changePct)})`}
              tone={latest.change >= 0 ? "up" : "down"}
            />
            <AssetMetric label="현금" value={won(latest.cash)} />
            <AssetMetric label="최고 순자산" value={won(latest.high)} />
            <AssetMetric label="최저 순자산" value={won(latest.low)} />
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            매도 후 현금화된 금액은 순자산에 남고, 주식평가액은 줄어듭니다. 외부 입출금은 이벤트로 기록하면 흐름 해석이 쉬워집니다.
          </p>
        </div>
      </div>

      <div className="border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <span className="text-[11px] font-medium text-muted-foreground">입출금/메모 이벤트</span>
          <button
            type="button"
            onClick={() => setShowForm((value) => !value)}
            className="text-[11px] text-primary hover:underline"
          >
            + 이벤트 추가
          </button>
        </div>

        {showForm && (
          <div className="flex flex-wrap items-end gap-2 border-b border-border bg-[var(--secondary)] px-4 py-3">
            <label className="grid gap-1 text-[10px] text-muted-foreground">
              날짜/시간
              <input
                type="datetime-local"
                value={form.ts}
                onChange={(event) => setForm((prev) => ({ ...prev, ts: event.target.value }))}
                className="h-8 border border-border bg-background px-2 font-data text-xs text-foreground"
              />
            </label>
            <label className="grid gap-1 text-[10px] text-muted-foreground">
              라벨
              <input
                value={form.label}
                onChange={(event) => setForm((prev) => ({ ...prev, label: event.target.value }))}
                placeholder="입금, 매도 현금화"
                className="h-8 w-40 border border-border bg-background px-2 text-xs text-foreground"
              />
            </label>
            <label className="grid gap-1 text-[10px] text-muted-foreground">
              금액
              <input
                type="number"
                value={form.amount}
                onChange={(event) => setForm((prev) => ({ ...prev, amount: event.target.value }))}
                placeholder="1000000"
                className="h-8 w-32 border border-border bg-background px-2 font-data text-xs text-foreground"
              />
            </label>
            <label className="grid gap-1 text-[10px] text-muted-foreground">
              타입
              <select
                value={form.type}
                onChange={(event) => setForm((prev) => ({ ...prev, type: event.target.value }))}
                className="h-8 border border-border bg-background px-2 text-xs text-foreground"
              >
                <option>입금</option>
                <option>출금</option>
                <option>기타</option>
              </select>
            </label>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !form.ts || !form.label}
              className="h-8 border border-primary bg-primary px-3 text-xs text-primary-foreground disabled:opacity-50"
            >
              {saving ? "저장 중" : "저장"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="h-8 border border-border px-3 text-xs text-muted-foreground"
            >
              취소
            </button>
          </div>
        )}

        {(events as EventOut[]).length === 0 && !showForm ? (
          <div className="flex h-12 items-center justify-center text-xs text-muted-foreground">
            이벤트 없음
          </div>
        ) : (
          (events as EventOut[]).map((event) => (
            <div
              key={event.id}
              className="flex items-center justify-between border-b border-border px-4 py-2 last:border-0 hover:bg-[var(--secondary)]"
            >
              <div className="flex items-center gap-2">
                <span className="border border-border px-1.5 py-0.5 font-data text-[10px] text-muted-foreground">
                  {EVENT_LABEL[event.type] ?? "EVT"}
                </span>
                <div>
                  <p className="text-xs text-foreground">{event.label}</p>
                  <p className="font-data text-[10px] text-muted-foreground">
                    {new Date(event.ts).toLocaleString("ko-KR")} · {event.type}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {event.amount !== 0 && (
                  <span className={`font-data text-xs ${event.amount >= 0 ? "text-gain" : "text-loss"}`}>
                    {signedWon(event.amount)}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => handleDelete(event.id)}
                  className="text-[11px] text-muted-foreground hover:text-error"
                >
                  삭제
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
