# M7: 기술적 지표 + 알림 시스템

**날짜**: 2026-05-30  
**브랜치**: feat/nextjs-fastapi-migration  
**상태**: 승인됨

---

## 목표

Bloomberg 터미널의 CandleChart 위젯에 기술적 지표(MA·볼린저밴드·RSI·MACD·Volume)를 통합하고,
사용자가 가격·지표 조건을 등록해 인앱 토스트 + 히스토리 패널로 알림을 받는 시스템을 구축한다.

---

## 범위 (In-scope)

- CandleChart에 지표 4패널 통합 (toggle ON/OFF)
- 지표: MA(5/20/60/120일), 볼린저밴드(20일 ±2σ), RSI(14일), MACD(12/26/9), VolumeMA(20일)
- 알림 조건: `price_above`, `price_below`, `rsi_above`, `rsi_below`, `ma_golden_cross`, `ma_dead_cross`
- AlertPanel 위젯 (조건 등록 + 히스토리)
- 인앱 토스트 알림 (10초 폴링)
- APScheduler 1분 주기 알림 체크

## 범위 (Out-of-scope)

- 브라우저 Push 알림 (OS 레벨)
- 이메일/SMS 알림
- 실시간 WebSocket 스트리밍 지표
- 지표 파라미터 커스터마이즈 (기간 변경)

---

## 아키텍처

```
[CandleChart] ──GET /api/candles?indicators=true──→ [candles.py]
                                                         │
                                              [core/indicators.py]
                                               MA/BB/RSI/MACD/VolMA
                                                         │
                                              lightweight-charts 4패널
                                              pane 0: 캔들+MA+볼린저
                                              pane 1: Volume+VolumeMA
                                              pane 2: RSI + 30/70선
                                              pane 3: MACD+Signal+Hist

[AlertPanel] ──POST /api/alerts──────────────→ [alerts.py]
                                              user_alerts 테이블

[scheduler.py] ─1분 주기─────────────────────→ alert_check_job
                                              현재가 + RSI 계산
                                              조건 충족 → user_alert_events

[useAlerts hook] ─10초 폴링─────────────────→ GET /api/alerts/events/unread
                                              새 이벤트 → 토스트 + 히스토리
```

---

## 백엔드

### core/indicators.py (신규)

```python
def compute_indicators(df: pd.DataFrame) -> dict:
    """
    입력: OHLCV DataFrame (index=date, columns=Open/High/Low/Close/Volume)
    출력: {
        ma: {5: [...], 20: [...], 60: [...], 120: [...]},
        bollinger: {upper: [...], middle: [...], lower: [...]},
        rsi: [...],
        macd: {macd: [...], signal: [...], histogram: [...]},
        volume_ma: [...],
    }
    각 리스트는 {"time": "YYYY-MM-DD", "value": float} 형태
    NaN은 None으로 직렬화
    """
```

계산 방식:
- **MA**: `df.Close.rolling(period).mean()`
- **볼린저밴드**: middle = MA(20), upper/lower = middle ± 2 × `df.Close.rolling(20).std()`
- **RSI**: `_compute_rsi()` from `core/factors/technical.py` 재사용 (rolling 방식)
- **MACD**: EMA(12) − EMA(26) = MACD, EMA(9, MACD) = Signal, MACD − Signal = Histogram
- **VolumeMA**: `df.Volume.rolling(20).mean()`

### api/models.py 추가

```python
class IndicatorPoint(BaseModel):
    time: str
    value: float | None

class IndicatorsData(BaseModel):
    ma: dict[str, list[IndicatorPoint]]   # "5", "20", "60", "120"
    bollinger: dict[str, list[IndicatorPoint]]  # "upper", "middle", "lower"
    rsi: list[IndicatorPoint]
    macd: dict[str, list[IndicatorPoint]]  # "macd", "signal", "histogram"
    volume_ma: list[IndicatorPoint]

class CandlesOut(BaseModel):             # 기존 모델 확장
    ticker: str
    period: str
    candles: list[CandleItem]
    indicators: IndicatorsData | None = None

class AlertIn(BaseModel):
    ticker: str
    condition_type: Literal[
        "price_above", "price_below",
        "rsi_above", "rsi_below",
        "ma_golden_cross", "ma_dead_cross"
    ]
    condition_value: float | None = None  # golden/dead cross는 None

class AlertOut(AlertIn):
    id: int
    enabled: bool
    created_at: datetime

class AlertEventOut(BaseModel):
    id: int
    ticker: str
    condition_type: str
    condition_value: float | None
    triggered_price: float
    triggered_at: datetime
    read: bool
```

### api/routers/candles.py 수정

```python
@router.get("", response_model=CandlesOut)
def get_candles(
    ticker: str = Query(...),
    period: str = Query("3M"),
    indicators: bool = Query(False),   # 추가
    user: CurrentUser = Depends(current_user),
):
    ...
    if indicators:
        out.indicators = compute_indicators(df)
    return out
```

### api/routers/alerts.py (신규)

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/alerts` | 내 알림 조건 목록 |
| POST | `/api/alerts` | 알림 조건 등록 |
| DELETE | `/api/alerts/{id}` | 알림 조건 삭제 |
| GET | `/api/alerts/events` | 알림 이벤트 전체 히스토리 (최근 50개) |
| GET | `/api/alerts/events/unread` | 미읽음 이벤트 (폴링용) |
| POST | `/api/alerts/events/read` | 전체 읽음 처리 |

### DuckDB 스키마 추가 (core/repository.py)

```sql
CREATE SEQUENCE IF NOT EXISTS user_alerts_id_seq;
CREATE TABLE IF NOT EXISTS user_alerts (
    id           INTEGER DEFAULT nextval('user_alerts_id_seq') PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    ticker       VARCHAR NOT NULL,
    condition_type VARCHAR NOT NULL,
    condition_value DOUBLE,
    enabled      BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE SEQUENCE IF NOT EXISTS user_alert_events_id_seq;
CREATE TABLE IF NOT EXISTS user_alert_events (
    id              INTEGER DEFAULT nextval('user_alert_events_id_seq') PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    alert_id        INTEGER,
    ticker          VARCHAR NOT NULL,
    condition_type  VARCHAR NOT NULL,
    condition_value DOUBLE,
    triggered_price DOUBLE NOT NULL,
    triggered_at    TIMESTAMP DEFAULT NOW(),
    read            BOOLEAN DEFAULT FALSE
);
```

### core/scheduler.py 수정

`alert_check_job` 추가 (1분 주기):
1. `repo.get_enabled_alerts()` — 활성 알림 전체 로드
2. 티커별로 현재가 조회 (`_price_provider.get_current_prices`)
3. `rsi_above` / `rsi_below` 조건이 있는 경우에만 RSI 계산 (최근 20일 캔들)
4. `ma_golden_cross` / `ma_dead_cross`는 MA5 vs MA20 비교 (최근 25일 캔들)
5. 조건 충족 → `repo.insert_alert_event()` 삽입
6. 중복 방지: 같은 alert_id가 최근 1시간 내 이미 이벤트를 발생시켰으면 스킵

---

## 프론트엔드

### CandleChart.tsx 재작성

**헤더 변경**
- 기존 기간 버튼(5D/1M/3M/6M/1Y) 유지
- 우측에 `[지표]` 토글 버튼 추가 (ON → `?indicators=true` 요청)

**lightweight-charts 4패널 구성**

| pane | 내용 | 높이 비율 |
|---|---|---|
| 0 | 캔들스틱 + MA 오버레이(4개) + 볼린저밴드(3선) | ~55% |
| 1 | Volume 히스토그램 + VolumeMA 선 | ~15% |
| 2 | RSI 선 + 30/70 수평 기준선 | ~15% |
| 3 | MACD 히스토그램 + MACD선 + Signal선 | ~15% |

**MA 색상**
- MA5: `#ff9f0a` (orange)
- MA20: `#ffd60a` (yellow)
- MA60: `#30d158` (green)
- MA120: `#64d2ff` (blue)

**볼린저밴드**
- upper/lower: `rgba(100, 210, 255, 0.4)` 점선
- middle: `rgba(100, 210, 255, 0.7)` 실선

**RSI 기준선**: 30 (`#ff453a` 점선), 70 (`#30d158` 점선)

**MACD**
- MACD선: `#0a84ff`
- Signal선: `#ff9f0a`
- Histogram: 양수 `rgba(48, 209, 88, 0.6)`, 음수 `rgba(255, 69, 58, 0.6)`

### AlertPanel.tsx (신규 위젯)

```
┌─ ALERTS ─────────────────────────────┐
│ [+ 새 알림 추가]                       │
│ Ticker: [AAPL    ] Type: [▼ RSI 과매도]│
│ Value:  [30      ]         [추가]      │
├──────────────────────────────────────┤
│ ACTIVE CONDITIONS                    │
│ AAPL  RSI < 30              [삭제]   │
│ SPY   Price > 550           [삭제]   │
├──────────────────────────────────────┤
│ ALERT HISTORY                        │
│ 14:32  AAPL  RSI 28.4 (< 30)        │
│ 11:05  SPY   $551.2 (> 550)         │
└──────────────────────────────────────┘
```

- WidgetRegistry에 `"alerts"` 키로 등록
- CommandPalette에 "알림 패널 추가" 명령 추가

### hooks/useAlerts.ts (신규)

```typescript
export function useAlerts() {
  // 10초 폴링 — /api/alerts/events/unread
  // 새 이벤트 발생 시: 토스트 표시 + 읽음 처리
  // 반환: { events, conditions, addAlert, deleteAlert }
}
```

토스트: shadcn/ui `toast` 또는 간단한 자체 구현 (`AlertToast.tsx`)

### lib/types.ts 추가

```typescript
export interface IndicatorPoint { time: string; value: number | null }
export interface IndicatorsData {
  ma: Record<string, IndicatorPoint[]>
  bollinger: Record<string, IndicatorPoint[]>
  rsi: IndicatorPoint[]
  macd: Record<string, IndicatorPoint[]>
  volume_ma: IndicatorPoint[]
}
export interface AlertCondition {
  id: number; ticker: string; condition_type: string
  condition_value: number | null; enabled: boolean; created_at: string
}
export interface AlertEvent {
  id: number; ticker: string; condition_type: string
  condition_value: number | null; triggered_price: number
  triggered_at: string; read: boolean
}
```

---

## 테스트

| 파일 | 케이스 |
|---|---|
| `tests/test_indicators.py` | MA/볼린저/RSI/MACD 계산 정확도 (알려진 값 비교) |
| `tests/test_alerts_api.py` | CRUD + unread 폴링 + 읽음 처리 |
| `tests/test_alert_check.py` | `price_above` / `rsi_below` / `ma_golden_cross` 조건 발화 |

---

## 완료 기준

1. `GET /api/candles?ticker=AAPL&period=3M&indicators=true` — MA/볼린저/RSI/MACD/VolumeMA 데이터 반환
2. CandleChart 지표 토글 ON → 4패널 표시 (캔들+MA+볼린저 / Volume+VolumeMA / RSI+기준선 / MACD)
3. AlertPanel에서 `AAPL RSI < 30` 조건 등록 → 스케줄러 체크 → 조건 충족 시 토스트 표시 + 히스토리 기록
4. pytest 3개 파일 전부 통과
