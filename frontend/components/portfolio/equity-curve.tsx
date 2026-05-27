"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  Brush, CartesianGrid, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { portfolioApi } from "@/lib/api";
import type { EventOut, SnapshotHistory } from "@/lib/types";

interface Props { history: SnapshotHistory[] }

const RANGES = ["1H", "6H", "24H", "3D", "7D", "30D"] as const;
type Range = typeof RANGES[number];
const RANGE_MS: Record<Range, number> = {
  "1H": 3_600_000, "6H": 21_600_000, "24H": 86_400_000,
  "3D": 259_200_000, "7D": 604_800_000, "30D": 2_592_000_000,
};

const MONO = "var(--font-roboto-mono, 'Roboto Mono', monospace)";
const EVENT_ICON: Record<string, string> = { "입금": "💰", "출금": "💳", "기타": "📌" };

function fmtCompact(v: number): string {
  const sign = v < 0 ? "−" : v > 0 ? "+" : "";
  const abs = Math.abs(v);
  if (abs >= 100_000_000) return `${sign}₩${(abs / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${sign}₩${(abs / 10_000).toFixed(0)}만`;
  return `${sign}₩${abs.toLocaleString("ko-KR")}`;
}

function fmtTick(ts: string): string {
  const d = new Date(ts);
  const MM = String(d.getMonth() + 1).padStart(2, "0");
  const DD = String(d.getDate()).padStart(2, "0");
  const HH = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${MM}-${DD} ${HH}:${mm}`;
}

interface FormState { ts: string; label: string; amount: string; type: string }
const EMPTY_FORM: FormState = { ts: "", label: "", amount: "", type: "입금" };

export function EquityCurve({ history }: Props) {
  const [range, setRange] = useState<Range>("7D");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const { data: events = [], mutate: mutateEvents } =
    useSWR("/api/portfolio/events", portfolioApi.events);

  // 범위 필터링 + 차트 데이터 변환
  const filtered = useMemo(() => {
    const cutoff = Date.now() - RANGE_MS[range];
    return [...history]
      .reverse()
      .filter((h) => new Date(h.ts).getTime() >= cutoff)
      .map((h) => ({ ts: h.ts, equity: h.total_equity_krw, total: h.total_with_cash_krw }));
  }, [history, range]);

  // 통계 행
  const stats = useMemo(() => {
    if (filtered.length === 0) return null;
    const totals = filtered.map((d) => d.total);
    return {
      current: filtered[filtered.length - 1].total,
      change: filtered[filtered.length - 1].total - filtered[0].total,
      max: Math.max(...totals),
      min: Math.min(...totals),
    };
  }, [filtered]);

  // 차트 범위 내 이벤트 → 가장 가까운 스냅샷 ts로 매핑
  const visibleEvents = useMemo(() => {
    if (filtered.length === 0) return [] as (EventOut & { nearestTs: string })[];
    const start = new Date(filtered[0].ts).getTime();
    const end = new Date(filtered[filtered.length - 1].ts).getTime();
    return (events as EventOut[])
      .filter((e) => {
        const t = new Date(e.ts).getTime();
        return t >= start && t <= end;
      })
      .map((e) => {
        const t = new Date(e.ts).getTime();
        const nearest = filtered.reduce((prev, curr) =>
          Math.abs(new Date(curr.ts).getTime() - t) <
          Math.abs(new Date(prev.ts).getTime() - t)
            ? curr
            : prev
        );
        return { ...e, nearestTs: nearest.ts };
      });
  }, [events, filtered]);

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

  if (filtered.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs text-muted-foreground">
        스냅샷 없음 — 5분 후 자동 생성됩니다.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* 헤더: 타이틀 + 범위 버튼 */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-muted-foreground">자산 추이</span>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-2 py-0.5 text-[10px] border rounded-sm font-mono transition-colors ${
                r === range
                  ? "border-primary text-primary bg-blue-50"
                  : "border-border text-muted-foreground hover:border-primary hover:text-primary"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* 통계 행 */}
      {stats && (
        <div className="grid grid-cols-4 border border-border divide-x divide-border bg-card">
          {(
            [
              { label: "현재", value: fmtCompact(stats.current).replace(/^[+−]/, ""), className: "text-foreground" },
              {
                label: "변동",
                value: fmtCompact(stats.change),
                className: stats.change >= 0 ? "text-gain" : "text-loss",
              },
              { label: "최고", value: fmtCompact(stats.max).replace(/^[+−]/, ""), className: "text-foreground" },
              { label: "최저", value: fmtCompact(stats.min).replace(/^[+−]/, ""), className: "text-foreground" },
            ] as { label: string; value: string; className: string }[]
          ).map(({ label, value, className }) => (
            <div key={label} className="flex flex-col items-center py-2">
              <span className="text-[9px] text-muted-foreground mb-0.5">{label}</span>
              <span className={`font-data text-xs font-medium ${className}`}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* 메인 차트 */}
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={filtered} margin={{ top: 20, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="4 4" stroke="#EDEEF1" />
          <XAxis
            dataKey="ts"
            tickFormatter={fmtTick}
            tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }}
            minTickGap={80}
          />
          <YAxis
            tickFormatter={(v) => `₩${(v / 1_000_000).toFixed(0)}M`}
            tick={{ fontSize: 10, fill: "#666666", fontFamily: MONO }}
            width={55}
          />
          <Tooltip
            formatter={(v: unknown, name: unknown) => [
              typeof v === "number" ? `₩${v.toLocaleString("ko-KR")}` : String(v),
              name === "equity" ? "주식평가액" : "순자산",
            ]}
            labelFormatter={(ts) => fmtTick(String(ts))}
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid #BEC1C6",
              borderRadius: 4,
              fontFamily: MONO,
              fontSize: 12,
            }}
          />
          <Legend
            formatter={(v) => (v === "equity" ? "주식평가액" : "순자산")}
            wrapperStyle={{ fontSize: 11, fontFamily: MONO, color: "#666666" }}
          />
          {visibleEvents.map((e) => (
            <ReferenceLine
              key={e.id}
              x={e.nearestTs}
              stroke="#E8812A"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              label={{ value: e.label, position: "top", fontSize: 10, fill: "#E8812A", fontFamily: MONO }}
            />
          ))}
          <Line type="monotone" dataKey="equity" stroke="#1375EC" strokeWidth={2} dot={false} />
          <Line
            type="monotone"
            dataKey="total"
            stroke="#BEC1C6"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
          />
          <Brush
            dataKey="ts"
            height={24}
            stroke="#1375EC"
            travellerWidth={8}
            tickFormatter={fmtTick}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* 이벤트 섹션 */}
      <div className="border border-border bg-card">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <span className="text-[11px] font-medium text-muted-foreground">이벤트</span>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="text-[11px] text-primary hover:underline"
          >
            + 이벤트 추가
          </button>
        </div>

        {showForm && (
          <div className="px-4 py-3 border-b border-border flex flex-wrap gap-2 items-end bg-[#F9FAFC]">
            <div className="space-y-1">
              <label className="block text-[10px] text-muted-foreground">날짜/시간</label>
              <input
                type="datetime-local"
                value={form.ts}
                onChange={(e) => setForm((f) => ({ ...f, ts: e.target.value }))}
                className="h-8 border border-border rounded-sm px-2 text-xs font-mono"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-[10px] text-muted-foreground">라벨</label>
              <input
                type="text"
                value={form.label}
                onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                placeholder="5월 월급"
                className="h-8 w-32 border border-border rounded-sm px-2 text-xs"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-[10px] text-muted-foreground">금액 (선택)</label>
              <input
                type="number"
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                placeholder="7900000"
                className="h-8 w-28 border border-border rounded-sm px-2 text-xs font-mono"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-[10px] text-muted-foreground">타입</label>
              <select
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="h-8 border border-border rounded-sm px-2 text-xs"
              >
                <option>입금</option>
                <option>출금</option>
                <option>기타</option>
              </select>
            </div>
            <button
              onClick={handleSave}
              disabled={saving || !form.ts || !form.label}
              className="h-8 px-3 bg-primary text-white text-xs rounded-sm disabled:opacity-50"
            >
              {saving ? "저장 중…" : "저장"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="h-8 px-3 border border-border text-xs rounded-sm text-muted-foreground"
            >
              취소
            </button>
          </div>
        )}

        {(events as EventOut[]).length === 0 && !showForm && (
          <div className="flex h-12 items-center justify-center text-xs text-muted-foreground">
            이벤트 없음
          </div>
        )}

        {(events as EventOut[]).map((e) => (
          <div
            key={e.id}
            className="flex items-center justify-between px-4 py-2 border-b border-border last:border-0 hover:bg-[#F4F5F7]"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">{EVENT_ICON[e.type] ?? "📌"}</span>
              <div>
                <p className="text-xs text-foreground">{e.label}</p>
                <p className="font-mono text-[10px] text-muted-foreground">
                  {new Date(e.ts).toLocaleString("ko-KR", {
                    year: "numeric", month: "2-digit", day: "2-digit",
                    hour: "2-digit", minute: "2-digit",
                  })}{" "}
                  · {e.type}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {e.amount !== 0 && (
                <span
                  className={`font-data text-xs font-medium ${
                    e.amount > 0 ? "text-gain" : "text-loss"
                  }`}
                >
                  {e.amount > 0 ? "+" : ""}
                  {(e.amount / 10_000).toLocaleString()}만원
                </span>
              )}
              <button
                onClick={() => handleDelete(e.id)}
                className="text-[11px] text-muted-foreground hover:text-error"
              >
                삭제
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
