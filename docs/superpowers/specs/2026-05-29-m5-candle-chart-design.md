# M5 캔들 차트 설계

**날짜:** 2026-05-29  
**범위:** `MarketsPanel` Row 2 Center Panel — lightweight-charts 기반 캔들스틱 차트 연결

---

## 1. 목표

`MarketsPanel.tsx` Row 2의 CHART 패널 placeholder(`"캔들 차트 — M5에서 연결"`)를 실제 캔들스틱 차트로 교체한다.

**완료 기준:**
- `/terminal` → Markets 탭에서 CHART 패널에 실제 캔들스틱이 렌더링된다.
- Watchlist 종목 클릭 시 차트가 해당 종목으로 전환된다.
- 기간 버튼(5D · 1M · 3M · 6M · 1Y) 클릭 시 차트 범위가 바뀐다.

---

## 2. 아키텍처

### 데이터 흐름

```
Watchlist 클릭
  → commandStore.setFocusedTicker(ticker)   [zustand, 기존]
  → CandleChart (ticker prop 변경 감지)
  → SWR: GET /api/candles?ticker=SPY&period=3M
  → FastAPI candles 라우터
  → fetch_ohlcv(tickers, start, end)        [기존 DuckDB 캐시 + KIS/yfinance]
  → CandleItem[] JSON 반환
  → lightweight-charts createChart() 업데이트
```

### 기본 종목 폴백

`focusedTicker`(zustand) → null이면 보유종목 첫 번째 → 그것도 없으면 `"SPY"`

---

## 3. 백엔드

### 3-1. Pydantic 모델 (`api/models.py` 추가)

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

### 3-2. 라우터 (`api/routers/candles.py` 신규)

```
GET /api/candles
  params: ticker (str), period (str, default="3M")
  auth: current_user 필요
  logic:
    period → (start, end) 날짜 계산
    fetch_ohlcv([ticker], start, end) 호출
    DataFrame → CandleItem[] 변환
  returns: CandlesOut
```

**period → 날짜 매핑:**

| period | 일수 |
|--------|------|
| 5D     | 7    |
| 1M     | 35   |
| 3M     | 95   |
| 6M     | 185  |
| 1Y     | 370  |

(비영업일 포함 오차분 +5일 여유)

### 3-3. 라우터 등록 (`api/main.py`)

`from api.routers import candles` 추가 후 `app.include_router(candles.router)`.

---

## 4. 프론트엔드

### 4-1. 의존성

```bash
uv pip install  # (백엔드 불필요)
npm install lightweight-charts  # 프론트엔드
```

lightweight-charts v5 — vanilla JS Canvas 기반, React ref로 mount/unmount 관리.

### 4-2. 타입 (`frontend/lib/types.ts` 추가)

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

### 4-3. API 클라이언트 (`frontend/lib/api.ts` 추가)

```typescript
export const candlesApi = {
  get: (ticker: string, period: string): Promise<CandlesOut> =>
    fetcher(`/api/candles?ticker=${ticker}&period=${period}`),
};
```

### 4-4. `CandleChart.tsx` (신규)

**위치:** `frontend/components/terminal/widgets/CandleChart.tsx`

**인터페이스:**
```typescript
interface Props {
  ticker: string;
  // period는 컴포넌트 내부 state — 기간 버튼이 CandleChart 헤더에 있으므로 외부에서 관리하지 않음
}
```

**구현:**
- `useRef<HTMLDivElement>` → container
- `useEffect`: `createChart(container, options)` — Bloomberg 다크 테마 CSS 변수 적용
  - `background: #0a0a0a`, `textColor: var(--color-text-secondary)`
  - `grid.vertLines/horzLines: #1a1a1a`
- `addCandlestickSeries()`: up `#30d158`, down `#ff453a`
- `addHistogramSeries()`: 볼륨 (opacity 0.4)
- `ResizeObserver` → `chart.applyOptions({ width, height })` 반응형
- SWR `candlesApi.get(ticker, period)` → `series.setData(candles)`
- `useEffect` cleanup: `chart.remove()`

**헤더 UI (패널 내 포함):**
- 좌: `CHART` 라벨
- 우: `{ticker}` + 현재가 + 등락 + 기간 버튼(5D · 1M · 3M · 6M · 1Y)

### 4-5. `MarketsPanel.tsx` 수정

```typescript
// 추가
import { useCommandStore } from "@/lib/stores/command";
import { holdingsApi } from "@/lib/api";
import { CandleChart } from "../widgets/CandleChart";

// Row 2 Center Panel 내부
const focusedTicker = useCommandStore(s => s.focusedTicker);
const { data: holdings } = useSWR("/api/holdings", holdingsApi.list);
const ticker = focusedTicker ?? holdings?.[0]?.ticker ?? "SPY";

// placeholder 교체 (period는 CandleChart 내부에서 관리)
<CandleChart ticker={ticker} />
```

`WatchlistWidget`은 이미 `onClick → setFocusedTicker`를 호출하므로 수정 불필요.

---

## 5. 신규/수정 파일 목록

| 파일 | 변경 |
|------|------|
| `api/routers/candles.py` | 신규 |
| `api/models.py` | `CandleItem`, `CandlesOut` 추가 |
| `api/main.py` | candles 라우터 등록 |
| `frontend/lib/types.ts` | `CandleItem`, `CandlesOut` 추가 |
| `frontend/lib/api.ts` | `candlesApi` 추가 |
| `frontend/components/terminal/widgets/CandleChart.tsx` | 신규 |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | CandleChart 연결 |

---

## 6. 테스트 기준

- `GET /api/candles?ticker=SPY&period=3M` → 200 + candles 배열 반환
- `GET /api/candles?ticker=SPY&period=3M` (인증 없음) → 401
- 빈 candles (상장폐지 종목 등) → 프론트에서 "데이터 없음" 표시
- Watchlist 클릭 → 차트 종목 전환 확인
- 기간 버튼 클릭 → 범위 변경 확인
- 패널 리사이즈 → 차트 반응형 확인
