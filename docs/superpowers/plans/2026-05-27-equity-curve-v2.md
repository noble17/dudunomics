# Equity Curve v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자산 추이 차트에 시간 범위 필터·통계 행·줌 브러시·이벤트 시스템을 추가하고 기존 tooltip/X축 버그를 수정한다.

**Architecture:** 백엔드에 `portfolio_events` 테이블과 CRUD API를 추가하고, 프론트엔드 `EquityCurve` 컴포넌트를 전면 재작성한다. 이벤트 데이터는 `EquityCurve` 내부 `useSWR`로 자체 조회해 dashboard.tsx 계층 변경을 최소화한다.

**Tech Stack:** Python/FastAPI/DuckDB (백엔드), React/Next.js/Recharts/SWR (프론트엔드)

---

## 파일 변경 목록

| 파일 | 변경 |
|------|------|
| `core/repository.py` | `portfolio_events` 테이블 DDL + `get_events`, `insert_event`, `delete_event` 추가 |
| `api/models.py` | `EventIn`, `EventOut` 모델 추가 |
| `api/routers/portfolio.py` | GET/POST/DELETE `/api/portfolio/events` 엔드포인트 추가 |
| `tests/test_events_repo.py` | repository 함수 테스트 (신규) |
| `tests/test_events_api.py` | API 엔드포인트 테스트 (신규) |
| `frontend/lib/types.ts` | `EventOut` 타입 추가 |
| `frontend/lib/api.ts` | `portfolioApi.events`, `addEvent`, `deleteEvent` 추가 |
| `frontend/app/portfolio/page.tsx` | history limit 8640으로 변경 |
| `frontend/components/portfolio/equity-curve.tsx` | 전면 재작성 |

---

## Task 1: DB 스키마 + Repository 함수

**Files:**
- Modify: `core/repository.py`
- Create: `tests/test_events_repo.py`

- [ ] **Step 1: repository.py — DDL에 portfolio_events 테이블 추가**

`core/repository.py`의 `_init_schema` 함수 내 `ddl` 문자열에서 `backtest_runs_id_seq` 시퀀스 생성문 바로 뒤에 다음을 추가한다:

```python
    CREATE TABLE IF NOT EXISTS portfolio_events (
        id INTEGER PRIMARY KEY,
        ts TIMESTAMP NOT NULL,
        label TEXT NOT NULL,
        amount INTEGER DEFAULT 0,
        type TEXT DEFAULT '기타'
    );

    CREATE SEQUENCE IF NOT EXISTS portfolio_events_id_seq START 1;
```

- [ ] **Step 2: repository.py — 이벤트 CRUD 함수 3개 추가**

`core/repository.py`의 `get_latest_fundamental` 함수 위에 다음을 추가한다:

```python
# ── Portfolio Events ──────────────────────────────────────────────────────────

def get_events() -> list[dict]:
    with session() as s:
        rows = s.execute(
            text("SELECT * FROM portfolio_events ORDER BY ts DESC")
        ).mappings().all()
        return [dict(r) for r in rows]


def insert_event(ts: datetime, label: str, amount: int, type_: str) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('portfolio_events_id_seq')")).fetchone()
        event_id = row[0]
        s.execute(text("""
            INSERT INTO portfolio_events (id, ts, label, amount, type)
            VALUES (:id, :ts, :label, :amount, :type)
        """), {"id": event_id, "ts": ts, "label": label, "amount": amount, "type": type_})
        s.commit()
    return event_id


def delete_event(event_id: int) -> None:
    with session() as s:
        s.execute(text("DELETE FROM portfolio_events WHERE id = :id"), {"id": event_id})
        s.commit()
```

- [ ] **Step 3: 실패 테스트 작성**

`tests/test_events_repo.py` 파일을 생성한다:

```python
import pytest
from datetime import datetime
import core.repository as repo


def test_get_events_empty():
    assert repo.get_events() == []


def test_insert_and_get_events():
    id1 = repo.insert_event(datetime(2026, 5, 23, 21, 9), "5월 월급", 7_900_000, "입금")
    id2 = repo.insert_event(datetime(2026, 5, 14, 20, 5), "카드값", -2_000_000, "출금")

    events = repo.get_events()
    assert len(events) == 2
    # ORDER BY ts DESC → 5월 23일이 먼저
    assert events[0]["label"] == "5월 월급"
    assert events[0]["amount"] == 7_900_000
    assert events[0]["type"] == "입금"
    assert events[1]["label"] == "카드값"
    assert isinstance(id1, int)
    assert isinstance(id2, int)


def test_delete_event():
    id1 = repo.insert_event(datetime(2026, 5, 1, 10, 0), "테스트", 0, "기타")
    assert len(repo.get_events()) == 1

    repo.delete_event(id1)
    assert repo.get_events() == []


def test_delete_nonexistent_event_does_not_raise():
    repo.delete_event(9999)  # 존재하지 않아도 에러 없음
```

- [ ] **Step 4: 테스트 실행 — 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics
.venv/bin/pytest tests/test_events_repo.py -v
```

Expected: `FAILED` — `get_events` 미정의 등 오류

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
.venv/bin/pytest tests/test_events_repo.py -v
```

Expected:
```
PASSED tests/test_events_repo.py::test_get_events_empty
PASSED tests/test_events_repo.py::test_insert_and_get_events
PASSED tests/test_events_repo.py::test_delete_event
PASSED tests/test_events_repo.py::test_delete_nonexistent_event_does_not_raise
4 passed
```

- [ ] **Step 6: 커밋**

```bash
git add core/repository.py tests/test_events_repo.py
git commit -m "feat: add portfolio_events table and repository CRUD"
```

---

## Task 2: API 모델 + 이벤트 엔드포인트

**Files:**
- Modify: `api/models.py`
- Modify: `api/routers/portfolio.py`
- Create: `tests/test_events_api.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_events_api.py`를 생성한다:

```python
import pytest


def test_get_events_empty(client):
    res = client.get("/api/portfolio/events")
    assert res.status_code == 200
    assert res.json() == []


def test_add_event(client):
    payload = {
        "ts": "2026-05-23T21:09:00",
        "label": "5월 월급",
        "amount": 7_900_000,
        "type": "입금",
    }
    res = client.post("/api/portfolio/events", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] >= 1
    assert data["label"] == "5월 월급"
    assert data["amount"] == 7_900_000
    assert data["type"] == "입금"


def test_add_event_minimal(client):
    """amount, type 생략 시 기본값 적용"""
    res = client.post("/api/portfolio/events", json={"ts": "2026-05-01T10:00:00", "label": "메모"})
    assert res.status_code == 200
    data = res.json()
    assert data["amount"] == 0
    assert data["type"] == "기타"


def test_delete_event(client):
    res = client.post("/api/portfolio/events", json={
        "ts": "2026-05-01T10:00:00", "label": "삭제테스트", "amount": 0, "type": "기타"
    })
    event_id = res.json()["id"]

    del_res = client.delete(f"/api/portfolio/events/{event_id}")
    assert del_res.status_code == 200
    assert del_res.json() == {"ok": True}

    assert client.get("/api/portfolio/events").json() == []


def test_delete_nonexistent_event(client):
    res = client.delete("/api/portfolio/events/9999")
    assert res.status_code == 200  # 존재하지 않아도 ok
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
.venv/bin/pytest tests/test_events_api.py -v
```

Expected: `FAILED` — 404 또는 라우터 없음 오류

- [ ] **Step 3: api/models.py에 EventIn, EventOut 추가**

`api/models.py`의 `FxRateOut` 클래스 위에 추가한다:

```python
class EventIn(BaseModel):
    ts: datetime
    label: str
    amount: int = 0
    type: str = "기타"


class EventOut(EventIn):
    id: int
```

- [ ] **Step 4: api/routers/portfolio.py에 이벤트 엔드포인트 추가**

`portfolio.py` 상단 import에 `EventIn`, `EventOut`을 추가한다:

```python
from api.models import EventIn, EventOut, PortfolioRow, PortfolioSnapshot, SnapshotHistory
```

그 다음 `_get_usdkrw` 함수 위에 아래 3개 엔드포인트를 추가한다:

```python
@router.get("/events", response_model=list[EventOut])
def get_events():
    return repo.get_events()


@router.post("/events", response_model=EventOut)
def add_event(body: EventIn):
    event_id = repo.insert_event(
        ts=body.ts, label=body.label, amount=body.amount, type_=body.type
    )
    return EventOut(id=event_id, ts=body.ts, label=body.label, amount=body.amount, type=body.type)


@router.delete("/events/{event_id}")
def delete_event(event_id: int):
    repo.delete_event(event_id)
    return {"ok": True}
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
.venv/bin/pytest tests/test_events_api.py tests/test_events_repo.py -v
```

Expected:
```
PASSED tests/test_events_api.py::test_get_events_empty
PASSED tests/test_events_api.py::test_add_event
PASSED tests/test_events_api.py::test_add_event_minimal
PASSED tests/test_events_api.py::test_delete_event
PASSED tests/test_events_api.py::test_delete_nonexistent_event
PASSED tests/test_events_repo.py::test_get_events_empty
... (4 more)
9 passed
```

- [ ] **Step 6: 기존 테스트 회귀 확인**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 모든 기존 테스트 포함 전체 통과

- [ ] **Step 7: 커밋**

```bash
git add api/models.py api/routers/portfolio.py tests/test_events_api.py
git commit -m "feat: add portfolio events API endpoints"
```

---

## Task 3: 프론트엔드 타입 + API 클라이언트 + history limit

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/portfolio/page.tsx`

- [ ] **Step 1: frontend/lib/types.ts에 EventOut 추가**

`HoldingOut` 인터페이스 아래에 추가한다:

```typescript
export interface EventOut {
  id: number;
  ts: string;
  label: string;
  amount: number;
  type: string;
}
```

- [ ] **Step 2: frontend/lib/api.ts 업데이트**

상단 import에 `EventOut`을 추가한다:

```typescript
import type {
  BacktestRunIn, BacktestRunOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
} from "./types";
```

`portfolioApi` 객체를 다음으로 교체한다:

```typescript
export const portfolioApi = {
  current: () => request<PortfolioSnapshot>("/api/portfolio/current"),
  history: (limit = 8640) =>
    request<SnapshotHistory[]>(`/api/portfolio/history?limit=${limit}`),
  events: () => request<EventOut[]>("/api/portfolio/events"),
  addEvent: (body: Omit<EventOut, "id">) =>
    request<EventOut>("/api/portfolio/events", { method: "POST", body: JSON.stringify(body) }),
  deleteEvent: (id: number) =>
    request<{ ok: boolean }>(`/api/portfolio/events/${id}`, { method: "DELETE" }),
};
```

- [ ] **Step 3: frontend/app/portfolio/page.tsx — history SWR key 업데이트**

`history` SWR 훅의 key를 limit을 반영한 URL로 변경한다:

```typescript
const { data: history } =
  useSWR("/api/portfolio/history?limit=8640", () => portfolioApi.history(), { refreshInterval: 60_000 });
```

- [ ] **Step 4: 타입 오류 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 오류 없음 (또는 이미 존재하던 오류만)

- [ ] **Step 5: 커밋**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/app/portfolio/page.tsx
git commit -m "feat: add EventOut type and events API client methods"
```

---

## Task 4: EquityCurve 컴포넌트 전면 재작성

**Files:**
- Modify: `frontend/components/portfolio/equity-curve.tsx`

- [ ] **Step 1: equity-curve.tsx 전면 교체**

`frontend/components/portfolio/equity-curve.tsx`를 아래 내용으로 교체한다:

```typescript
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
            tickCount={6}
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
```

- [ ] **Step 2: 타입 오류 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -40
```

Expected: 오류 없음

- [ ] **Step 3: 브라우저에서 동작 확인**

서버 실행 확인 (`uv run uvicorn api.main:app --reload --port 8000` + Next.js dev). 포트폴리오 페이지 열기.

체크리스트:
- [ ] 범위 버튼 (1H/6H/24H/3D/7D/30D) 클릭 시 차트 범위 변경
- [ ] 통계 행 (현재/변동/최고/최저) 값이 선택 범위 기준으로 표시
- [ ] Tooltip이 주식평가액과 순자산을 **다른 값**으로 표시 (현금 있을 때)
- [ ] X축에 날짜 + 시간 (MM-DD HH:mm) 표시
- [ ] 줌 브러시 드래그 시 차트 확대
- [ ] `+ 이벤트 추가` 클릭 시 인라인 폼 표시
- [ ] 이벤트 저장 시 목록에 추가됨, 저장된 범위 내 이벤트가 차트에 주황 점선으로 표시
- [ ] 이벤트 삭제 버튼 동작

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/portfolio/equity-curve.tsx
git commit -m "feat: rewrite EquityCurve with range filter, stats, zoom brush, events"
```

---

## Task 5: 전체 회귀 테스트

- [ ] **Step 1: 백엔드 전체 테스트**

```bash
cd /Users/user/Development/private/dudunomics
.venv/bin/pytest tests/ -v
```

Expected: 전체 통과

- [ ] **Step 2: 최종 커밋**

모든 테스트 통과 확인 후 추가 변경이 있으면 커밋한다.
