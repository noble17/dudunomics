# M5 캔들 차트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `MarketsPanel` Row 2 CHART 패널 placeholder를 lightweight-charts 기반 캔들스틱 차트로 교체하고, Watchlist 클릭 시 종목이 자동 전환되도록 연결한다.

**Architecture:** FastAPI에 `GET /api/candles?ticker=SPY&period=3M` 엔드포인트를 신규 추가하고 기존 `fetch_ohlcv` DuckDB 캐시를 재사용한다. 프론트엔드는 `CandleChart.tsx`(lightweight-charts Canvas 렌더러)를 새로 만들고 MarketsPanel에서 `commandStore.focusedTicker`를 구독해 ticker를 전달한다.

**Tech Stack:** FastAPI · Pydantic v2 · `fetch_ohlcv` (DuckDB + KIS/yfinance) · lightweight-charts v4 · SWR · Zustand · TypeScript

---

## 파일 구조

| 파일 | 변경 |
|------|------|
| `api/models.py` | `CandleItem`, `CandlesOut` 모델 추가 |
| `api/routers/candles.py` | 신규 — `GET /api/candles` 라우터 |
| `api/main.py` | candles 라우터 등록 |
| `tests/test_candles_api.py` | 신규 — API 테스트 4개 |
| `frontend/lib/types.ts` | `CandleItem`, `CandlesOut` 타입 추가 |
| `frontend/lib/api.ts` | `candlesApi` 추가 |
| `frontend/components/terminal/widgets/CandleChart.tsx` | 신규 — 차트 컴포넌트 |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | CandleChart 연결 |

---

## Task 1: Pydantic 모델 추가

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: `CandleItem`, `CandlesOut` 모델을 `api/models.py` 끝에 추가**

`api/models.py` 파일 맨 끝에 추가:
```python
class CandleItem(BaseModel):
    time: str       # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandlesOut(BaseModel):
    ticker: str
    period: str
    candles: list[CandleItem]
```

- [ ] **Step 2: 임포트 확인 후 커밋**

```bash
cd /Users/user/Development/private/dudunomics
python3 -c "from api.models import CandleItem, CandlesOut; print('ok')"
```
Expected: `ok`

```bash
git add api/models.py
git commit -m "feat(m5): add CandleItem, CandlesOut Pydantic models"
```

---

## Task 2: candles 라우터 구현

**Files:**
- Create: `api/routers/candles.py`
- Modify: `api/main.py`

- [ ] **Step 1: `api/routers/candles.py` 파일 생성**

```python
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import current_user, CurrentUser
from core.data.prices_provider import fetch_ohlcv
from api.models import CandleItem, CandlesOut

router = APIRouter(prefix="/api/candles", tags=["candles"])

_PERIOD_DAYS: dict[str, int] = {
    "5D":  7,
    "1M":  35,
    "3M":  95,
    "6M":  185,
    "1Y":  370,
}


@router.get("", response_model=CandlesOut)
def get_candles(
    ticker: str = Query(..., description="티커 심볼 (예: SPY)"),
    period: str = Query("3M", description="기간: 5D | 1M | 3M | 6M | 1Y"),
    user: CurrentUser = Depends(current_user),
) -> CandlesOut:
    days = _PERIOD_DAYS.get(period.upper())
    if days is None:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 period: {period}. 5D|1M|3M|6M|1Y 중 선택.")

    end = date.today()
    start = end - timedelta(days=days)

    prices, _ = fetch_ohlcv([ticker.upper()], start, end)
    if prices.empty:
        return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=[])

    df = prices[ticker.upper()][["Open", "High", "Low", "Close", "Volume"]].dropna()

    candles = [
        CandleItem(
            time=ts.strftime("%Y-%m-%d"),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
        )
        for ts, row in df.iterrows()
    ]
    return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=candles)
```

- [ ] **Step 2: `api/main.py`에 candles 라우터 등록**

`api/main.py`의 quotes_router import 아래에 추가:
```python
from api.routers.candles import router as candles_router
```

`app.include_router(quotes_router)` 아래에 추가:
```python
app.include_router(candles_router)
```

- [ ] **Step 3: 문법 검사**

```bash
python3 -c "from api.routers.candles import router; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: 커밋**

```bash
git add api/routers/candles.py api/main.py
git commit -m "feat(m5): add GET /api/candles endpoint"
```

---

## Task 3: candles API 테스트

**Files:**
- Create: `tests/test_candles_api.py`

- [ ] **Step 1: 테스트 파일 생성**

```python
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch


def _make_fake_ohlcv(ticker: str = "SPY", n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    close = 500 + np.cumsum(rng.normal(0, 1, n))
    ticker_df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(50_000_000, 100_000_000, n).astype(float),
    }, index=idx)
    return pd.concat({ticker: ticker_df}, axis=1)


@pytest.fixture
def candles_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "candles@test.com", "password": "password123"})
    return c


def test_candles_structure(candles_client):
    fake = _make_fake_ohlcv("SPY", 60)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=3M")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "SPY"
    assert data["period"] == "3M"
    assert len(data["candles"]) == 60
    c = data["candles"][0]
    for field in ("time", "open", "high", "low", "close", "volume"):
        assert field in c, f"candle missing field: {field}"
    assert c["high"] >= c["low"]


def test_candles_empty_ticker(candles_client):
    """데이터 없는 종목은 빈 candles 배열 반환 (4xx 아님)."""
    with patch("api.routers.candles.fetch_ohlcv", return_value=(pd.DataFrame(), [])):
        res = candles_client.get("/api/candles?ticker=UNKNOWN&period=1M")
    assert res.status_code == 200
    assert res.json()["candles"] == []


def test_candles_invalid_period(candles_client):
    """지원하지 않는 period는 422."""
    res = candles_client.get("/api/candles?ticker=SPY&period=INVALID")
    assert res.status_code == 422


def test_candles_requires_auth(fresh_db, monkeypatch):
    """인증 없이 접근 시 401."""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/candles?ticker=SPY")
    assert res.status_code == 401
```

- [ ] **Step 2: 테스트 실패 확인 (TDD)**

```bash
cd /Users/user/Development/private/dudunomics
python3 -m pytest tests/test_candles_api.py -v 2>&1 | head -30
```
Expected: 4개 PASS (라우터가 이미 구현되어 있으므로)

- [ ] **Step 3: 커밋**

```bash
git add tests/test_candles_api.py
git commit -m "test(m5): add candles API tests (4 cases)"
```

---

## Task 4: 프론트엔드 타입 + API 클라이언트

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: `frontend/lib/types.ts` 끝에 타입 추가**

```typescript
export interface CandleItem {
  time: string;   // "YYYY-MM-DD"
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CandlesOut {
  ticker: string;
  period: string;
  candles: CandleItem[];
}
```

- [ ] **Step 2: `frontend/lib/api.ts` 상단 import에 `CandlesOut` 추가**

기존:
```typescript
import type {
  BacktestRunIn, BacktestRunOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
  WorkspaceLayout,
  QuotesOut,
} from "./types";
```

변경 후:
```typescript
import type {
  BacktestRunIn, BacktestRunOut, CandlesOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
  WorkspaceLayout,
  QuotesOut,
} from "./types";
```

- [ ] **Step 3: `frontend/lib/api.ts` 끝에 `candlesApi` 추가**

파일 맨 끝에 추가 (기존 `quotesApi` 아래):
```typescript
export const candlesApi = {
  get: (ticker: string, period: string) =>
    request<CandlesOut>(`/api/candles?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`),
};
```

- [ ] **Step 4: TypeScript 타입 검사**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: 에러 없음

- [ ] **Step 5: 커밋**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(m5): add CandleItem type and candlesApi client"
```

---

## Task 5: lightweight-charts 설치 + CandleChart 컴포넌트

**Files:**
- Create: `frontend/components/terminal/widgets/CandleChart.tsx`

- [ ] **Step 1: lightweight-charts 설치**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npm install lightweight-charts@4
```
Expected: `added 1 package` (또는 유사 메시지)

- [ ] **Step 2: `CandleChart.tsx` 파일 생성**

`frontend/components/terminal/widgets/CandleChart.tsx`:

```typescript
"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import useSWR from "swr";
import { candlesApi } from "@/lib/api";
import type { CandleItem } from "@/lib/types";

type Period = "5D" | "1M" | "3M" | "6M" | "1Y";
const PERIODS: Period[] = ["5D", "1M", "3M", "6M", "1Y"];

interface Props {
  ticker: string;
}

export function CandleChart({ ticker }: Props) {
  const [period, setPeriod] = useState<Period>("3M");
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleSeriesRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeSeriesRef = useRef<any>(null);

  const { data, isLoading } = useSWR(
    ["candles", ticker, period],
    () => candlesApi.get(ticker, period),
    { dedupingInterval: 60_000 },
  );

  // 차트 마운트 / 언마운트
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#636366",
      },
      grid: {
        vertLines: { color: "#1a1a1a" },
        horzLines: { color: "#1a1a1a" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1a1a1a" },
      timeScale: { borderColor: "#1a1a1a", timeVisible: false },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#30d158",
      downColor: "#ff453a",
      borderUpColor: "#30d158",
      borderDownColor: "#ff453a",
      wickUpColor: "#30d158",
      wickDownColor: "#ff453a",
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const observer = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // 데이터 업데이트 (ticker 또는 period 변경 시)
  useEffect(() => {
    if (!data?.candles.length || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    candleSeriesRef.current.setData(
      data.candles.map((c: CandleItem) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    volumeSeriesRef.current.setData(
      data.candles.map((c: CandleItem) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(48,209,88,0.35)" : "rgba(255,69,58,0.35)",
      })),
    );

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  const candles = data?.candles ?? [];
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const change = last && prev ? last.close - prev.close : 0;
  const changePct = prev?.close ? (change / prev.close) * 100 : 0;
  const isUp = change >= 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 헤더 */}
      <div className="px-3 py-1.5 shrink-0 border-b border-[var(--color-border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">
            CHART
          </span>
          {last && (
            <>
              <span className="text-[11px] font-mono font-bold text-[var(--color-text-primary)]">
                {ticker}
              </span>
              <span className="text-[10px] font-mono text-[var(--color-text-primary)]">
                {last.close.toFixed(2)}
              </span>
              <span
                className={`text-[9px] font-mono ${
                  isUp ? "text-[#30d158]" : "text-[#ff453a]"
                }`}
              >
                {isUp ? "▲" : "▼"}
                {Math.abs(change).toFixed(2)} ({changePct.toFixed(2)}%)
              </span>
            </>
          )}
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-1.5 py-0.5 text-[9px] font-mono border transition-colors ${
                p === period
                  ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* 차트 */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && !data && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">로딩 중…</span>
          </div>
        )}
        {!isLoading && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">데이터 없음</span>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript 타입 검사**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: 에러 없음 (또는 기존 에러만)

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/terminal/widgets/CandleChart.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(m5): add CandleChart component with lightweight-charts"
```

---

## Task 6: MarketsPanel 연결 + 브라우저 검증

**Files:**
- Modify: `frontend/components/terminal/panels/MarketsPanel.tsx`

- [ ] **Step 1: MarketsPanel.tsx import 추가**

`frontend/components/terminal/panels/MarketsPanel.tsx` 파일 상단 import 섹션을 아래와 같이 교체:

기존:
```typescript
import useSWR from "swr";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { quotesApi, portfolioApi } from "@/lib/api";
```

변경 후:
```typescript
import useSWR from "swr";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { quotesApi, portfolioApi, holdingsApi } from "@/lib/api";
import { useCommandStore } from "@/lib/stores/command";
import { CandleChart } from "@/components/terminal/widgets/CandleChart";
```

- [ ] **Step 2: MarketsPanel 컴포넌트 내부에 ticker 계산 추가**

`MarketsPanel` 컴포넌트 함수 안, 기존 `useSWR` 호출들 아래에 추가:
```typescript
const focusedTicker = useCommandStore((s) => s.focusedTicker);
const { data: holdings } = useSWR("/api/holdings", holdingsApi.list, { dedupingInterval: 30_000 });
const chartTicker = focusedTicker ?? holdings?.[0]?.ticker ?? "SPY";
```

- [ ] **Step 3: CHART placeholder를 CandleChart로 교체**

기존 코드 (`MarketsPanel.tsx:107-117` 범위):
```typescript
        {/* 중: Chart placeholder (기본 50%) */}
        <Panel defaultSize={50} minSize={20} className="flex flex-col overflow-hidden border-x border-[var(--color-border)]">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            CHART
          </div>
          <div className="flex-1 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">
              캔들 차트 — M5에서 연결
            </span>
          </div>
        </Panel>
```

교체 후:
```typescript
        {/* 중: Chart (기본 50%) */}
        <Panel defaultSize={50} minSize={20} className="flex flex-col overflow-hidden border-x border-[var(--color-border)]">
          <CandleChart ticker={chartTicker} />
        </Panel>
```

- [ ] **Step 4: TypeScript 타입 검사**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: 에러 없음

- [ ] **Step 5: 커밋**

```bash
git add frontend/components/terminal/panels/MarketsPanel.tsx
git commit -m "feat(m5): wire CandleChart into MarketsPanel Row 2"
```

- [ ] **Step 6: 개발 서버 기동 + 브라우저 검증**

```bash
# 백엔드 (이미 실행 중이면 생략)
cd /Users/user/Development/private/dudunomics
uv run uvicorn api.main:app --reload --port 8000 &

# 프론트엔드
cd frontend
npm run dev
```

브라우저에서 `http://localhost:3333/terminal` 접속 후 확인:
1. Markets 탭 → Row 2 CHART 패널에 캔들스틱 렌더링 확인
2. 기간 버튼(5D · 1M · 3M · 6M · 1Y) 클릭 → 차트 범위 변경 확인
3. Watchlist 종목 클릭 → 헤더 종목명 + 차트 변경 확인
4. CHART 패널 리사이즈(드래그) → 차트 반응형 확인

- [ ] **Step 7: 최종 백엔드 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics
python3 -m pytest tests/test_candles_api.py -v
```
Expected: 4개 PASSED

- [ ] **Step 8: M5 완료 커밋 및 메모리 업데이트**

```bash
git add -p   # 남은 변경사항 없는지 확인
```
