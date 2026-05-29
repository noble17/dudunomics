# M7: 기술적 지표 + 알림 시스템 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CandleChart에 MA·볼린저·RSI·MACD·Volume 지표를 통합하고, 가격·지표 조건 기반 인앱 알림 시스템을 구축한다.

**Architecture:** 백엔드에서 pandas로 지표를 계산해 `/api/candles?indicators=true`로 반환, lightweight-charts v4의 `priceScaleId`+`scaleMargins` 조합으로 4구역 차트를 렌더링. 알림 조건은 DuckDB에 저장하고 APScheduler가 1분 주기로 체크해 `user_alert_events`에 삽입, 프론트는 10초 폴링으로 토스트를 띄운다.

**Tech Stack:** Python/pandas, FastAPI, APScheduler, DuckDB, lightweight-charts v4.2.3, React/SWR, TypeScript

---

## 파일 맵

| 동작 | 파일 |
|---|---|
| Create | `core/indicators.py` |
| Create | `api/routers/alerts.py` |
| Create | `tests/test_indicators.py` |
| Create | `tests/test_alerts_api.py` |
| Create | `tests/test_alert_check.py` |
| Create | `frontend/components/terminal/widgets/AlertPanel.tsx` |
| Create | `frontend/hooks/useAlerts.ts` |
| Modify | `core/repository.py` — user_alerts·user_alert_events 테이블 + 함수 |
| Modify | `core/scheduler.py` — alert_check_job 추가 |
| Modify | `api/models.py` — 지표·알림 모델 추가 |
| Modify | `api/routers/candles.py` — indicators 파라미터 추가 |
| Modify | `api/main.py` — alerts 라우터 등록 |
| Modify | `frontend/lib/types.ts` — 지표·알림 타입 추가 |
| Modify | `frontend/lib/api.ts` — alertsApi + candlesApi 확장 |
| Modify | `frontend/components/terminal/widgets/CandleChart.tsx` — 4구역 차트 |
| Modify | `frontend/components/terminal/WidgetRegistry.ts` — AlertPanel 등록 |

---

## Task 1: DB 스키마 + Repository 알림 함수

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: `_init_schema` DDL에 두 테이블 추가**

`core/repository.py`의 `ddl` 문자열에서 `user_workspaces` 블록 바로 뒤, 닫는 `"""` 직전에 아래를 삽입한다.

```python
    CREATE SEQUENCE IF NOT EXISTS user_alerts_id_seq START 1;
    CREATE TABLE IF NOT EXISTS user_alerts (
        id              INTEGER DEFAULT nextval('user_alerts_id_seq') PRIMARY KEY,
        user_id         INTEGER NOT NULL,
        ticker          VARCHAR NOT NULL,
        condition_type  VARCHAR NOT NULL,
        condition_value DOUBLE,
        enabled         BOOLEAN DEFAULT TRUE,
        created_at      TIMESTAMP DEFAULT current_timestamp
    );

    CREATE SEQUENCE IF NOT EXISTS user_alert_events_id_seq START 1;
    CREATE TABLE IF NOT EXISTS user_alert_events (
        id              INTEGER DEFAULT nextval('user_alert_events_id_seq') PRIMARY KEY,
        user_id         INTEGER NOT NULL,
        alert_id        INTEGER,
        ticker          VARCHAR NOT NULL,
        condition_type  VARCHAR NOT NULL,
        condition_value DOUBLE,
        triggered_price DOUBLE NOT NULL,
        triggered_at    TIMESTAMP DEFAULT current_timestamp,
        read            BOOLEAN DEFAULT FALSE
    );
```

- [ ] **Step 2: repository 알림 함수 8개 추가**

파일 끝에 아래를 추가한다.

```python
# ── 알림 조건 CRUD ──────────────────────────────────────────

def create_alert(user_id: int, ticker: str, condition_type: str, condition_value: float | None) -> int:
    with session() as s:
        row = s.execute(text("""
            INSERT INTO user_alerts (user_id, ticker, condition_type, condition_value)
            VALUES (:u, :t, :ct, :cv)
            RETURNING id
        """), {"u": user_id, "t": ticker.upper(), "ct": condition_type, "cv": condition_value}).fetchone()
        s.commit()
        return row[0]


def get_user_alerts(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, enabled, created_at
            FROM user_alerts WHERE user_id = :u AND enabled = TRUE
            ORDER BY created_at DESC
        """), {"u": user_id}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2],
                 "condition_value": r[3], "enabled": r[4], "created_at": r[5]} for r in rows]


def delete_user_alert(user_id: int, alert_id: int) -> bool:
    with session() as s:
        result = s.execute(text(
            "DELETE FROM user_alerts WHERE id = :id AND user_id = :u"
        ), {"id": alert_id, "u": user_id})
        s.commit()
        return result.rowcount > 0


def get_all_enabled_alerts() -> list[dict]:
    """스케줄러용 — 전체 사용자 활성 알림."""
    with session() as s:
        rows = s.execute(text("""
            SELECT id, user_id, ticker, condition_type, condition_value
            FROM user_alerts WHERE enabled = TRUE
        """)).fetchall()
        return [{"id": r[0], "user_id": r[1], "ticker": r[2],
                 "condition_type": r[3], "condition_value": r[4]} for r in rows]


def has_recent_alert_event(alert_id: int, minutes: int = 60) -> bool:
    """같은 alert_id가 최근 N분 내 이미 발화했는지 확인 (중복 방지)."""
    with session() as s:
        row = s.execute(text("""
            SELECT COUNT(*) FROM user_alert_events
            WHERE alert_id = :aid
              AND triggered_at >= current_timestamp - INTERVAL (CAST(:m AS VARCHAR) || ' minutes')
        """), {"aid": alert_id, "m": minutes}).fetchone()
        return row[0] > 0


def insert_alert_event(user_id: int, alert_id: int, ticker: str,
                       condition_type: str, condition_value: float | None,
                       triggered_price: float) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO user_alert_events
              (user_id, alert_id, ticker, condition_type, condition_value, triggered_price)
            VALUES (:u, :aid, :t, :ct, :cv, :price)
        """), {"u": user_id, "aid": alert_id, "t": ticker, "ct": condition_type,
               "cv": condition_value, "price": triggered_price})
        s.commit()


def get_alert_events(user_id: int, limit: int = 50) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, triggered_price, triggered_at, read
            FROM user_alert_events WHERE user_id = :u
            ORDER BY triggered_at DESC LIMIT :lim
        """), {"u": user_id, "lim": limit}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2], "condition_value": r[3],
                 "triggered_price": r[4], "triggered_at": r[5], "read": r[6]} for r in rows]


def get_unread_alert_events(user_id: int) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT id, ticker, condition_type, condition_value, triggered_price, triggered_at, read
            FROM user_alert_events WHERE user_id = :u AND read = FALSE
            ORDER BY triggered_at DESC
        """), {"u": user_id}).fetchall()
        return [{"id": r[0], "ticker": r[1], "condition_type": r[2], "condition_value": r[3],
                 "triggered_price": r[4], "triggered_at": r[5], "read": r[6]} for r in rows]


def mark_all_alert_events_read(user_id: int) -> None:
    with session() as s:
        s.execute(text(
            "UPDATE user_alert_events SET read = TRUE WHERE user_id = :u AND read = FALSE"
        ), {"u": user_id})
        s.commit()
```

- [ ] **Step 3: DB 스키마 smoke test 실행**

```bash
cd /Users/user/Development/private/dudunomics
uv run pytest tests/test_workspace_api.py -v --tb=short
```

기존 workspace 테스트가 여전히 통과하면 스키마 추가가 안전한 것.

- [ ] **Step 4: 커밋**

```bash
git add core/repository.py
git commit -m "feat(M7): user_alerts + user_alert_events 테이블 + repository 함수"
```

---

## Task 2: core/indicators.py (TDD)

**Files:**
- Create: `core/indicators.py`
- Create: `tests/test_indicators.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_indicators.py` 생성:

```python
import math
import numpy as np
import pandas as pd
import pytest
from core.indicators import compute_indicators


def _make_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
    }, index=idx)


def test_compute_indicators_keys():
    df = _make_df(200)
    result = compute_indicators(df)
    assert set(result.keys()) == {"ma", "bollinger", "rsi", "macd", "volume_ma"}
    assert set(result["ma"].keys()) == {"5", "20", "60", "120"}
    assert set(result["bollinger"].keys()) == {"upper", "middle", "lower"}
    assert set(result["macd"].keys()) == {"macd", "signal", "histogram"}


def test_ma5_length_and_format():
    df = _make_df(200)
    result = compute_indicators(df)
    ma5 = result["ma"]["5"]
    # MA5는 처음 4개 NaN이므로 200-4=196개
    assert len(ma5) == 196
    assert "time" in ma5[0]
    assert "value" in ma5[0]
    assert isinstance(ma5[0]["time"], str)
    assert isinstance(ma5[0]["value"], float)


def test_ma120_requires_120_days():
    df = _make_df(200)
    result = compute_indicators(df)
    ma120 = result["ma"]["120"]
    # MA120는 처음 119개 NaN → 200-119=81개
    assert len(ma120) == 81


def test_bollinger_upper_ge_lower():
    df = _make_df(200)
    result = compute_indicators(df)
    for u, l in zip(result["bollinger"]["upper"], result["bollinger"]["lower"]):
        assert u["value"] >= l["value"]


def test_rsi_range():
    df = _make_df(200)
    result = compute_indicators(df)
    for pt in result["rsi"]:
        assert 0 <= pt["value"] <= 100


def test_macd_histogram_equals_macd_minus_signal():
    df = _make_df(200)
    result = compute_indicators(df)
    # 날짜가 같은 포인트들 비교
    macd_map = {pt["time"]: pt["value"] for pt in result["macd"]["macd"]}
    sig_map = {pt["time"]: pt["value"] for pt in result["macd"]["signal"]}
    hist_map = {pt["time"]: pt["value"] for pt in result["macd"]["histogram"]}
    for t in hist_map:
        if t in macd_map and t in sig_map:
            assert abs(hist_map[t] - (macd_map[t] - sig_map[t])) < 1e-6


def test_volume_ma_length():
    df = _make_df(200)
    result = compute_indicators(df)
    # VolumeMA20 → 처음 19개 NaN → 181개
    assert len(result["volume_ma"]) == 181


def test_short_df_returns_empty_for_long_ma():
    """데이터가 50개면 MA120은 빈 리스트."""
    df = _make_df(50)
    result = compute_indicators(df)
    assert result["ma"]["120"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_indicators.py -v --tb=short
```

Expected: `ImportError: No module named 'core.indicators'`

- [ ] **Step 3: `core/indicators.py` 구현**

```python
"""기술적 지표 계산 — MA·볼린저밴드·RSI·MACD·VolumeMA."""
from __future__ import annotations

import pandas as pd


def _to_points(index: pd.DatetimeIndex, series: pd.Series) -> list[dict]:
    """NaN 제외, {"time": "YYYY-MM-DD", "value": float} 리스트 반환."""
    return [
        {"time": ts.strftime("%Y-%m-%d"), "value": float(val)}
        for ts, val in zip(index, series)
        if pd.notna(val)
    ]


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    입력: OHLCV DataFrame (index=DatetimeIndex, columns 포함 Open/High/Low/Close/Volume)
    출력: {
        ma: {"5": [...], "20": [...], "60": [...], "120": [...]},
        bollinger: {"upper": [...], "middle": [...], "lower": [...]},
        rsi: [...],
        macd: {"macd": [...], "signal": [...], "histogram": [...]},
        volume_ma: [...],
    }
    각 리스트 원소: {"time": "YYYY-MM-DD", "value": float}
    NaN 구간(워밍업 기간)은 리스트에서 제외.
    """
    close = df["Close"]
    volume = df["Volume"]
    idx = df.index

    # ── MA ──────────────────────────────────────────────────
    ma = {
        str(p): _to_points(idx, close.rolling(p).mean())
        for p in (5, 20, 60, 120)
    }

    # ── 볼린저밴드 (20일, ±2σ) ─────────────────────────────
    bb_middle = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bollinger = {
        "upper": _to_points(idx, bb_middle + 2 * bb_std),
        "middle": _to_points(idx, bb_middle),
        "lower": _to_points(idx, bb_middle - 2 * bb_std),
    }

    # ── RSI (14일) ────────────────────────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = _to_points(idx, rsi_series)

    # ── MACD (12/26/9) ────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    macd = {
        "macd": _to_points(idx, macd_line),
        "signal": _to_points(idx, signal_line),
        "histogram": _to_points(idx, histogram),
    }

    # ── VolumeMA (20일) ───────────────────────────────────
    volume_ma = _to_points(idx, volume.rolling(20).mean())

    return {"ma": ma, "bollinger": bollinger, "rsi": rsi, "macd": macd, "volume_ma": volume_ma}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_indicators.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add core/indicators.py tests/test_indicators.py
git commit -m "feat(M7): core/indicators.py — MA·볼린저·RSI·MACD·VolumeMA 계산"
```

---

## Task 3: api/models.py + candles 엔드포인트 확장 (TDD)

**Files:**
- Modify: `api/models.py`
- Modify: `api/routers/candles.py`
- Modify: `tests/test_candles_api.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_candles_api.py` 끝에 아래 테스트를 추가한다.

```python
def test_candles_with_indicators(candles_client):
    """indicators=true 요청 시 ma/bollinger/rsi/macd/volume_ma 포함."""
    fake = _make_fake_ohlcv("SPY", 200)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=1Y&indicators=true")
    assert res.status_code == 200
    data = res.json()
    assert data["indicators"] is not None
    ind = data["indicators"]
    assert set(ind.keys()) == {"ma", "bollinger", "rsi", "macd", "volume_ma"}
    assert set(ind["ma"].keys()) == {"5", "20", "60", "120"}
    assert len(ind["ma"]["5"]) > 0
    pt = ind["ma"]["5"][0]
    assert "time" in pt and "value" in pt


def test_candles_without_indicators_returns_null(candles_client):
    """indicators 파라미터 없으면 indicators 필드가 null."""
    fake = _make_fake_ohlcv("SPY", 60)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=3M")
    assert res.status_code == 200
    assert res.json()["indicators"] is None
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_candles_api.py::test_candles_with_indicators -v
```

Expected: `KeyError: 'indicators'`

- [ ] **Step 3: `api/models.py`에 지표 + 알림 모델 추가**

파일 끝 `CandlesOut` 정의 아래에 다음을 추가한다.

```python
from typing import Literal

class IndicatorPoint(BaseModel):
    time: str
    value: float

class IndicatorsData(BaseModel):
    ma: dict[str, list[IndicatorPoint]]
    bollinger: dict[str, list[IndicatorPoint]]
    rsi: list[IndicatorPoint]
    macd: dict[str, list[IndicatorPoint]]
    volume_ma: list[IndicatorPoint]

class CandlesOut(BaseModel):          # 기존 모델 교체
    ticker: str
    period: str
    candles: list[CandleItem]
    indicators: IndicatorsData | None = None

AlertConditionType = Literal[
    "price_above", "price_below",
    "rsi_above", "rsi_below",
    "ma_golden_cross", "ma_dead_cross",
]

class AlertIn(BaseModel):
    ticker: str
    condition_type: AlertConditionType
    condition_value: float | None = None

class AlertOut(BaseModel):
    id: int
    ticker: str
    condition_type: str
    condition_value: float | None
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

주의: `models.py`에 이미 `CandlesOut`이 정의돼 있으면 해당 클래스를 교체한다. `from datetime import datetime`이 import에 없으면 추가한다.

- [ ] **Step 4: `api/routers/candles.py` 수정**

파일 상단 import에 추가:
```python
from core.indicators import compute_indicators
```

엔드포인트 시그니처를 아래로 교체한다:

```python
@router.get("", response_model=CandlesOut)
def get_candles(
    ticker: str = Query(..., description="티커 심볼 (예: SPY)"),
    period: str = Query("3M", description="기간: 5D | 1M | 3M | 6M | 1Y"),
    indicators: bool = Query(False, description="지표 데이터 포함 여부"),
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

    ind_data = None
    if indicators and len(df) >= 5:
        raw = compute_indicators(df)
        from api.models import IndicatorsData, IndicatorPoint
        ind_data = IndicatorsData(
            ma={k: [IndicatorPoint(**p) for p in v] for k, v in raw["ma"].items()},
            bollinger={k: [IndicatorPoint(**p) for p in v] for k, v in raw["bollinger"].items()},
            rsi=[IndicatorPoint(**p) for p in raw["rsi"]],
            macd={k: [IndicatorPoint(**p) for p in v] for k, v in raw["macd"].items()},
            volume_ma=[IndicatorPoint(**p) for p in raw["volume_ma"]],
        )

    return CandlesOut(ticker=ticker.upper(), period=period.upper(), candles=candles, indicators=ind_data)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_candles_api.py -v
```

Expected: 6 passed

- [ ] **Step 6: 커밋**

```bash
git add api/models.py api/routers/candles.py tests/test_candles_api.py
git commit -m "feat(M7): candles API indicators 파라미터 추가"
```

---

## Task 4: api/routers/alerts.py + 테스트 (TDD)

**Files:**
- Create: `api/routers/alerts.py`
- Create: `tests/test_alerts_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_alerts_api.py` 생성:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def alerts_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "alerts@test.com", "password": "password123"})
    return c


def test_list_alerts_empty(alerts_client):
    res = alerts_client.get("/api/alerts")
    assert res.status_code == 200
    assert res.json() == []


def test_create_and_list_alert(alerts_client):
    res = alerts_client.post("/api/alerts", json={
        "ticker": "AAPL",
        "condition_type": "price_above",
        "condition_value": 200.0,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ticker"] == "AAPL"
    assert data["condition_type"] == "price_above"
    assert data["condition_value"] == 200.0
    assert "id" in data

    res2 = alerts_client.get("/api/alerts")
    assert len(res2.json()) == 1


def test_create_cross_alert_no_value(alerts_client):
    """골든크로스 조건은 condition_value 없어도 된다."""
    res = alerts_client.post("/api/alerts", json={
        "ticker": "SPY",
        "condition_type": "ma_golden_cross",
    })
    assert res.status_code == 201
    assert res.json()["condition_value"] is None


def test_delete_alert(alerts_client):
    create_res = alerts_client.post("/api/alerts", json={
        "ticker": "TSLA",
        "condition_type": "rsi_below",
        "condition_value": 30.0,
    })
    alert_id = create_res.json()["id"]

    del_res = alerts_client.delete(f"/api/alerts/{alert_id}")
    assert del_res.status_code == 204

    list_res = alerts_client.get("/api/alerts")
    assert list_res.json() == []


def test_delete_other_users_alert_fails(fresh_db, monkeypatch):
    """다른 유저의 알림은 삭제 불가."""
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "user1@test.com", "password": "password123"})
    c.post("/api/auth/signup", json={"email": "user2@test.com", "password": "password123"})

    # user1이 알림 생성
    login1 = c.post("/api/auth/login", json={"email": "user1@test.com", "password": "password123"})
    token1 = login1.cookies.get("access_token")
    create_res = c.post("/api/alerts",
        json={"ticker": "AAPL", "condition_type": "price_above", "condition_value": 200.0},
        cookies={"access_token": token1},
    )
    alert_id = create_res.json()["id"]

    # user2가 삭제 시도
    login2 = c.post("/api/auth/login", json={"email": "user2@test.com", "password": "password123"})
    token2 = login2.cookies.get("access_token")
    del_res = c.delete(f"/api/alerts/{alert_id}", cookies={"access_token": token2})
    assert del_res.status_code == 404


def test_alert_events_empty(alerts_client):
    res = alerts_client.get("/api/alerts/events")
    assert res.status_code == 200
    assert res.json() == []


def test_unread_events_and_read(fresh_db, monkeypatch):
    """insert_alert_event → unread 조회 → 읽음 처리 후 unread=0."""
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    import core.repository as repo
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "ev@test.com", "password": "password123"})

    # user_id=1로 이벤트 직접 삽입
    repo.insert_alert_event(
        user_id=1, alert_id=None, ticker="AAPL",
        condition_type="price_above", condition_value=200.0, triggered_price=201.5,
    )

    unread = c.get("/api/alerts/events/unread")
    assert unread.status_code == 200
    assert len(unread.json()) == 1

    read_res = c.post("/api/alerts/events/read")
    assert read_res.status_code == 204

    unread2 = c.get("/api/alerts/events/unread")
    assert unread2.json() == []
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_alerts_api.py -v --tb=short
```

Expected: `404 Not Found` for all alert endpoints (router not registered yet)

- [ ] **Step 3: `api/routers/alerts.py` 작성**

```python
from fastapi import APIRouter, Depends, HTTPException
from core.auth.deps import current_user, CurrentUser
from api.models import AlertIn, AlertOut, AlertEventOut
import core.repository as repo

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(user: CurrentUser = Depends(current_user)):
    return repo.get_user_alerts(user.id)


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(body: AlertIn, user: CurrentUser = Depends(current_user)):
    alert_id = repo.create_alert(
        user_id=user.id,
        ticker=body.ticker,
        condition_type=body.condition_type,
        condition_value=body.condition_value,
    )
    alerts = repo.get_user_alerts(user.id)
    return next(a for a in alerts if a["id"] == alert_id)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: CurrentUser = Depends(current_user)):
    deleted = repo.delete_user_alert(user.id, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="알림 없음 또는 권한 없음")


@router.get("/events", response_model=list[AlertEventOut])
def get_alert_events(user: CurrentUser = Depends(current_user)):
    return repo.get_alert_events(user.id)


@router.get("/events/unread", response_model=list[AlertEventOut])
def get_unread_events(user: CurrentUser = Depends(current_user)):
    return repo.get_unread_alert_events(user.id)


@router.post("/events/read", status_code=204)
def mark_events_read(user: CurrentUser = Depends(current_user)):
    repo.mark_all_alert_events_read(user.id)
```

- [ ] **Step 4: `api/main.py`에 alerts 라우터 등록**

```python
# 기존 import 목록에 추가
from api.routers.alerts import router as alerts_router

# app.include_router(ai_router) 아래에 추가
app.include_router(alerts_router)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_alerts_api.py -v
```

Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add api/routers/alerts.py api/main.py tests/test_alerts_api.py
git commit -m "feat(M7): alerts CRUD API + events 엔드포인트"
```

---

## Task 5: APScheduler alert_check_job (TDD)

**Files:**
- Modify: `core/scheduler.py`
- Create: `tests/test_alert_check.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_alert_check.py` 생성:

```python
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
import core.repository as repo
from core.scheduler import alert_check_job


@pytest.fixture
def db_with_user(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    # 유저 생성 (id=1)
    repo.create_user("check@test.com", "hashed")
    return 1  # user_id


def _make_price_mock(ticker: str, price: float):
    from core.prices.base import Price
    return {ticker: Price(current=price, currency="USD")}


def _make_candle_df(n=50, close_values=None):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    if close_values is None:
        close_values = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "Open": [c * 0.99 for c in close_values],
        "High": [c * 1.01 for c in close_values],
        "Low":  [c * 0.98 for c in close_values],
        "Close": close_values,
        "Volume": [1_000_000.0] * n,
    }, index=idx)


def test_price_above_fires(db_with_user):
    user_id = db_with_user
    alert_id = repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 201.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["ticker"] == "AAPL"
    assert events[0]["condition_type"] == "price_above"
    assert events[0]["triggered_price"] == pytest.approx(201.0)


def test_price_above_no_fire_when_below(db_with_user):
    user_id = db_with_user
    repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 199.0)
        alert_check_job()

    assert repo.get_unread_alert_events(user_id) == []


def test_rsi_below_fires(db_with_user):
    user_id = db_with_user
    alert_id = repo.create_alert(user_id, "SPY", "rsi_below", 30.0)

    # RSI가 30 미만이 되도록 하락 추세 데이터 생성
    close_values = [100.0 - i * 2 for i in range(60)]  # 급격한 하락
    fake_df = _make_candle_df(60, close_values)
    fake_prices = pd.concat({"SPY": fake_df}, axis=1)

    with patch("core.scheduler._price_provider") as mock_pp, \
         patch("core.scheduler.fetch_ohlcv", return_value=(fake_prices, [])):
        mock_pp.get_current_prices.return_value = _make_price_mock("SPY", 1.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["condition_type"] == "rsi_below"


def test_dedup_prevents_double_fire(db_with_user):
    """같은 alert_id가 1시간 내 두 번 이상 발화하지 않는다."""
    user_id = db_with_user
    repo.create_alert(user_id, "AAPL", "price_above", 200.0)

    with patch("core.scheduler._price_provider") as mock_pp:
        mock_pp.get_current_prices.return_value = _make_price_mock("AAPL", 201.0)
        alert_check_job()
        alert_check_job()  # 두 번 호출

    assert len(repo.get_unread_alert_events(user_id)) == 1


def test_golden_cross_fires(db_with_user):
    """MA5가 MA20을 상향 돌파하면 golden cross 발화."""
    user_id = db_with_user
    repo.create_alert(user_id, "TSLA", "ma_golden_cross", None)

    # 처음 30일 하락(MA5 < MA20), 마지막 5일 급등(MA5 > MA20)
    close_values = [100.0 - i * 0.5 for i in range(30)] + [90.0 + i * 10 for i in range(10)]
    fake_df = _make_candle_df(40, close_values)
    fake_prices = pd.concat({"TSLA": fake_df}, axis=1)

    with patch("core.scheduler._price_provider") as mock_pp, \
         patch("core.scheduler.fetch_ohlcv", return_value=(fake_prices, [])):
        mock_pp.get_current_prices.return_value = _make_price_mock("TSLA", 180.0)
        alert_check_job()

    events = repo.get_unread_alert_events(user_id)
    assert len(events) == 1
    assert events[0]["condition_type"] == "ma_golden_cross"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_alert_check.py -v --tb=short
```

Expected: `AttributeError: module 'core.scheduler' has no attribute 'alert_check_job'`

- [ ] **Step 3: `core/scheduler.py` 수정**

파일 상단 import에 추가:
```python
from datetime import date, timedelta
import pandas as pd
from core.indicators import compute_indicators
from core.data.prices_provider import fetch_ohlcv
```

`create_scheduler()` 위에 다음 함수를 추가한다:

```python
def _check_condition(alert: dict, current_price: float, ohlcv_df: pd.DataFrame | None) -> bool:
    """알림 조건 충족 여부 반환."""
    ct = alert["condition_type"]
    cv = alert.get("condition_value")

    if ct == "price_above":
        return cv is not None and current_price > cv
    if ct == "price_below":
        return cv is not None and current_price < cv

    if ohlcv_df is None or len(ohlcv_df) < 21:
        return False

    indicators = compute_indicators(ohlcv_df)

    if ct in ("rsi_above", "rsi_below") and cv is not None:
        rsi_pts = indicators["rsi"]
        if not rsi_pts:
            return False
        last_rsi = rsi_pts[-1]["value"]
        return last_rsi > cv if ct == "rsi_above" else last_rsi < cv

    if ct in ("ma_golden_cross", "ma_dead_cross"):
        ma5 = indicators["ma"]["5"]
        ma20 = indicators["ma"]["20"]
        if len(ma5) < 2 or len(ma20) < 2:
            return False
        # 전일 MA5 < MA20, 당일 MA5 > MA20 → 골든크로스
        prev_cross = ma5[-2]["value"] < ma20[-2]["value"]
        curr_cross = ma5[-1]["value"] > ma20[-1]["value"]
        if ct == "ma_golden_cross":
            return prev_cross and curr_cross
        else:  # dead_cross
            return (not prev_cross) and (not curr_cross)

    return False


def alert_check_job():
    """활성 알림 조건 체크 — 조건 충족 시 user_alert_events 삽입 (1분 주기)."""
    try:
        alerts = repo.get_all_enabled_alerts()
        if not alerts:
            return

        # 티커별로 현재가 일괄 조회
        tickers = list({a["ticker"] for a in alerts})
        try:
            prices = _price_provider.get_current_prices(tickers)
        except Exception as e:
            log.warning("alert_check_job 시세 조회 실패: %s", e)
            return

        # RSI/MA 조건이 있는 티커만 OHLCV 조회
        indicator_tickers = {
            a["ticker"] for a in alerts
            if a["condition_type"] in ("rsi_above", "rsi_below", "ma_golden_cross", "ma_dead_cross")
        }
        ohlcv_cache: dict[str, pd.DataFrame] = {}
        if indicator_tickers:
            end = date.today()
            start = end - timedelta(days=60)
            for ticker in indicator_tickers:
                try:
                    prices_df, _ = fetch_ohlcv([ticker], start, end)
                    if not prices_df.empty and ticker in prices_df.columns.get_level_values(0):
                        ohlcv_cache[ticker] = prices_df[ticker][
                            ["Open", "High", "Low", "Close", "Volume"]
                        ].dropna()
                except Exception:
                    pass

        for alert in alerts:
            try:
                ticker = alert["ticker"]
                if ticker not in prices:
                    continue

                current_price = prices[ticker].current
                ohlcv_df = ohlcv_cache.get(ticker)

                if repo.has_recent_alert_event(alert["id"], minutes=60):
                    continue

                if _check_condition(alert, current_price, ohlcv_df):
                    repo.insert_alert_event(
                        user_id=alert["user_id"],
                        alert_id=alert["id"],
                        ticker=ticker,
                        condition_type=alert["condition_type"],
                        condition_value=alert.get("condition_value"),
                        triggered_price=current_price,
                    )
                    log.info("alert fired: user=%d ticker=%s type=%s price=%.2f",
                             alert["user_id"], ticker, alert["condition_type"], current_price)
            except Exception as e:
                log.error("alert check 오류 (alert_id=%d): %s", alert.get("id", -1), e)

    except Exception as e:
        log.error("alert_check_job 오류: %s", e)
```

`create_scheduler()` 함수에 아래 줄 추가:

```python
def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(snapshot_job, "interval", minutes=5, id="snapshot",
                      next_run_time=datetime.now())
    scheduler.add_job(alert_check_job, "interval", minutes=1, id="alert_check")  # 추가
    return scheduler
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_alert_check.py -v
```

Expected: 5 passed

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
uv run pytest tests/ -v --tb=short -q
```

Expected: 모든 테스트 통과

- [ ] **Step 6: 커밋**

```bash
git add core/scheduler.py tests/test_alert_check.py
git commit -m "feat(M7): APScheduler alert_check_job — 가격·RSI·MA 크로스 조건 체크"
```

---

## Task 6: Frontend 타입 + API 클라이언트

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: `frontend/lib/types.ts`에 타입 추가**

파일 끝에 추가:

```typescript
// ── 지표 ──────────────────────────────────────────────────
export interface IndicatorPoint {
  time: string
  value: number
}

export interface IndicatorsData {
  ma: Record<string, IndicatorPoint[]>        // "5" | "20" | "60" | "120"
  bollinger: Record<string, IndicatorPoint[]> // "upper" | "middle" | "lower"
  rsi: IndicatorPoint[]
  macd: Record<string, IndicatorPoint[]>      // "macd" | "signal" | "histogram"
  volume_ma: IndicatorPoint[]
}

// ── 알림 ──────────────────────────────────────────────────
export type AlertConditionType =
  | "price_above"
  | "price_below"
  | "rsi_above"
  | "rsi_below"
  | "ma_golden_cross"
  | "ma_dead_cross"

export interface AlertCondition {
  id: number
  ticker: string
  condition_type: AlertConditionType
  condition_value: number | null
  enabled: boolean
  created_at: string
}

export interface AlertEvent {
  id: number
  ticker: string
  condition_type: string
  condition_value: number | null
  triggered_price: number
  triggered_at: string
  read: boolean
}

export interface AlertIn {
  ticker: string
  condition_type: AlertConditionType
  condition_value?: number | null
}
```

기존 `CandlesOut` 타입을 찾아 `indicators` 필드를 추가한다:

```typescript
export interface CandlesOut {
  ticker: string
  period: string
  candles: CandleItem[]
  indicators?: IndicatorsData | null
}
```

- [ ] **Step 2: `frontend/lib/api.ts` 수정**

`candlesApi` 를 아래로 교체:

```typescript
export const candlesApi = {
  get: (ticker: string, period: string, indicators = false) =>
    request<CandlesOut>(
      `/api/candles?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}${indicators ? "&indicators=true" : ""}`
    ),
};
```

파일 끝에 `alertsApi` 추가:

```typescript
export const alertsApi = {
  list: () => request<AlertCondition[]>("/api/alerts"),
  create: (body: AlertIn) =>
    request<AlertCondition>("/api/alerts", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number) =>
    fetch(`/api/alerts/${id}`, { method: "DELETE", credentials: "include" }),
  events: () => request<AlertEvent[]>("/api/alerts/events"),
  unread: () => request<AlertEvent[]>("/api/alerts/events/unread"),
  markRead: () =>
    fetch("/api/alerts/events/read", { method: "POST", credentials: "include" }),
};
```

`api.ts` 상단 import에 새 타입들 추가 (`AlertCondition`, `AlertEvent`, `AlertIn`):

```typescript
import type {
  // ... 기존 타입들 ...
  AlertCondition, AlertEvent, AlertIn,
} from "./types";
```

- [ ] **Step 3: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit
```

Expected: 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(M7): 프론트 타입 + alertsApi + candlesApi indicators 파라미터"
```

---

## Task 7: CandleChart.tsx 재작성 (4구역 차트)

**Files:**
- Modify: `frontend/components/terminal/widgets/CandleChart.tsx`

- [ ] **Step 1: CandleChart.tsx 전체 교체**

아래 내용으로 파일을 완전히 교체한다.

```typescript
"use client";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import useSWR from "swr";
import { candlesApi } from "@/lib/api";
import type { CandleItem, IndicatorsData } from "@/lib/types";

type Period = "5D" | "1M" | "3M" | "6M" | "1Y";
const PERIODS: Period[] = ["5D", "1M", "3M", "6M", "1Y"];

interface Props { ticker: string }

// scaleMargins: 각 구역이 전체 차트 높이에서 차지하는 위치
// top=0.56 → 상단 56%는 여백(다른 구역이 사용), bottom=0.28 → 하단 28%도 여백
// 결과적으로 56%~72% 구간에 렌더
const SCALE_MARGINS = {
  candle:   { top: 0.00, bottom: 0.47 },  // 0~53%
  volume:   { top: 0.55, bottom: 0.30 },  // 55~70%
  rsi:      { top: 0.72, bottom: 0.15 },  // 72~85%
  macd:     { top: 0.87, bottom: 0.00 },  // 87~100%
} as const;

const MA_COLORS: Record<string, string> = {
  "5":   "#ff9f0a",
  "20":  "#ffd60a",
  "60":  "#30d158",
  "120": "#64d2ff",
};

export function CandleChart({ ticker }: Props) {
  const [period, setPeriod] = useState<Period>("3M");
  const [showIndicators, setShowIndicators] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<Record<string, any>>({});

  const { data, isLoading } = useSWR(
    ["candles", ticker, period, showIndicators],
    () => candlesApi.get(ticker, period, showIndicators),
    { dedupingInterval: 60_000 },
  );

  // 차트 생성 (마운트 시 1회)
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

    // ── 캔들 (메인 우측 스케일) ──────────────────────────────
    chart.priceScale("right").applyOptions({ scaleMargins: SCALE_MARGINS.candle });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#30d158", downColor: "#ff453a",
      borderUpColor: "#30d158", borderDownColor: "#ff453a",
      wickUpColor: "#30d158", wickDownColor: "#ff453a",
    });

    // ── 볼륨 ─────────────────────────────────────────────────
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol_scale",
      color: "rgba(100,100,100,0.4)",
    });
    chart.priceScale("vol_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.volume,
    });

    // ── RSI ──────────────────────────────────────────────────
    const rsiSeries = chart.addLineSeries({
      priceScaleId: "rsi_scale",
      color: "#bf5af2",
      lineWidth: 1,
    });
    chart.priceScale("rsi_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.rsi,
    });

    // ── MACD ─────────────────────────────────────────────────
    const macdLineSeries = chart.addLineSeries({
      priceScaleId: "macd_scale",
      color: "#0a84ff",
      lineWidth: 1,
    });
    const macdSignalSeries = chart.addLineSeries({
      priceScaleId: "macd_scale",
      color: "#ff9f0a",
      lineWidth: 1,
    });
    const macdHistSeries = chart.addHistogramSeries({
      priceScaleId: "macd_scale",
    });
    chart.priceScale("macd_scale").applyOptions({
      scaleMargins: SCALE_MARGINS.macd,
    });

    // ── MA (기본 포함) ────────────────────────────────────────
    const maSeriesMap: Record<string, ReturnType<typeof chart.addLineSeries>> = {};
    for (const [period, color] of Object.entries(MA_COLORS)) {
      maSeriesMap[period] = chart.addLineSeries({
        priceScaleId: "right",
        color,
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
      });
    }

    // ── 볼린저밴드 ────────────────────────────────────────────
    const bbUpper = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.6)",
      lineWidth: 1,
      lineStyle: 2, // dashed
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbMiddle = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.4)",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbLower = chart.addLineSeries({
      priceScaleId: "right",
      color: "rgba(100, 210, 255, 0.6)",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // ── VolumeMA ──────────────────────────────────────────────
    const volumeMaSeries = chart.addLineSeries({
      priceScaleId: "vol_scale",
      color: "#ff9f0a",
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    seriesRef.current = {
      candle: candleSeries, volume: volumeSeries,
      rsi: rsiSeries, macdLine: macdLineSeries,
      macdSignal: macdSignalSeries, macdHist: macdHistSeries,
      bbUpper, bbMiddle, bbLower, volumeMa: volumeMaSeries,
      ...Object.fromEntries(Object.entries(maSeriesMap).map(([k, v]) => [`ma${k}`, v])),
    };

    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = {};
    };
  }, []);

  // 데이터 업데이트
  useEffect(() => {
    const s = seriesRef.current;
    if (!data?.candles.length || !s.candle) return;

    s.candle.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
    })));

    s.volume.setData(data.candles.map((c: CandleItem) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? "rgba(48,209,88,0.35)" : "rgba(255,69,58,0.35)",
    })));

    const ind: IndicatorsData | null | undefined = data.indicators;

    // MA
    for (const p of ["5", "20", "60", "120"]) {
      const pts = ind?.ma?.[p] ?? [];
      s[`ma${p}`]?.setData(pts);
    }

    // 볼린저
    s.bbUpper?.setData(ind?.bollinger?.upper ?? []);
    s.bbMiddle?.setData(ind?.bollinger?.middle ?? []);
    s.bbLower?.setData(ind?.bollinger?.lower ?? []);

    // RSI
    s.rsi?.setData(ind?.rsi ?? []);

    // MACD
    s.macdLine?.setData(ind?.macd?.macd ?? []);
    s.macdSignal?.setData(ind?.macd?.signal ?? []);
    s.macdHist?.setData(
      (ind?.macd?.histogram ?? []).map((pt) => ({
        time: pt.time,
        value: pt.value,
        color: pt.value >= 0 ? "rgba(48,209,88,0.6)" : "rgba(255,69,58,0.6)",
      }))
    );

    // VolumeMA
    s.volumeMa?.setData(ind?.volume_ma ?? []);

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
          <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">CHART</span>
          {last && (
            <>
              <span className="text-[11px] font-mono font-bold text-[var(--color-text-primary)]">{ticker}</span>
              <span className="text-[10px] font-mono text-[var(--color-text-primary)]">{last.close.toFixed(2)}</span>
              <span className={`text-[9px] font-mono ${isUp ? "text-[#30d158]" : "text-[#ff453a]"}`}>
                {isUp ? "▲" : "▼"}{Math.abs(change).toFixed(2)} ({changePct.toFixed(2)}%)
              </span>
            </>
          )}
        </div>
        <div className="flex gap-1 items-center">
          <button
            onClick={() => setShowIndicators((v) => !v)}
            className={`px-1.5 py-0.5 text-[9px] font-mono border transition-colors ${
              showIndicators
                ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
            }`}
          >
            지표
          </button>
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

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit
```

Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/terminal/widgets/CandleChart.tsx
git commit -m "feat(M7): CandleChart 4구역 지표 패널 (MA·볼린저·RSI·MACD·VolumeMA)"
```

---

## Task 8: useAlerts 훅 + AlertPanel 위젯

**Files:**
- Create: `frontend/hooks/useAlerts.ts`
- Create: `frontend/components/terminal/widgets/AlertPanel.tsx`

- [ ] **Step 1: `frontend/hooks/useAlerts.ts` 작성**

```typescript
"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { alertsApi } from "@/lib/api";
import type { AlertCondition, AlertEvent, AlertIn } from "@/lib/types";

interface Toast {
  id: number
  message: string
}

let _toastId = 0;

export function useAlerts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seenIds = useRef<Set<number>>(new Set());

  const { data: conditions = [], mutate: mutateConditions } =
    useSWR<AlertCondition[]>("/api/alerts", alertsApi.list, { refreshInterval: 30_000 });

  const { data: unread = [], mutate: mutateUnread } =
    useSWR<AlertEvent[]>("/api/alerts/events/unread", alertsApi.unread, { refreshInterval: 10_000 });

  // 새 미읽음 이벤트 → 토스트
  useEffect(() => {
    const newEvents = unread.filter((e) => !seenIds.current.has(e.id));
    if (!newEvents.length) return;

    for (const ev of newEvents) {
      seenIds.current.add(ev.id);
      const msg = formatConditionMsg(ev);
      const id = ++_toastId;
      setToasts((prev) => [...prev, { id, message: msg }]);
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
    }

    alertsApi.markRead().then(() => mutateUnread());
  }, [unread, mutateUnread]);

  async function addAlert(body: AlertIn) {
    await alertsApi.create(body);
    mutateConditions();
  }

  async function removeAlert(id: number) {
    await alertsApi.delete(id);
    mutateConditions();
  }

  return { conditions, unread, toasts, addAlert, removeAlert };
}

export function formatConditionMsg(ev: AlertEvent): string {
  const price = ev.triggered_price.toFixed(2);
  switch (ev.condition_type) {
    case "price_above": return `${ev.ticker} $${price} ▲ ${ev.condition_value} 돌파`;
    case "price_below": return `${ev.ticker} $${price} ▼ ${ev.condition_value} 하향`;
    case "rsi_above":   return `${ev.ticker} RSI ${price} 과매수(>${ev.condition_value})`;
    case "rsi_below":   return `${ev.ticker} RSI ${price} 과매도(<${ev.condition_value})`;
    case "ma_golden_cross": return `${ev.ticker} MA 골든크로스 발생`;
    case "ma_dead_cross":   return `${ev.ticker} MA 데드크로스 발생`;
    default: return `${ev.ticker} 알림 발생`;
  }
}
```

- [ ] **Step 2: `frontend/components/terminal/widgets/AlertPanel.tsx` 작성**

```typescript
"use client";
import { useState } from "react";
import useSWR from "swr";
import { alertsApi } from "@/lib/api";
import { useAlerts, formatConditionMsg } from "@/hooks/useAlerts";
import type { AlertConditionType, AlertEvent } from "@/lib/types";

const CONDITION_OPTIONS: { value: AlertConditionType; label: string; needsValue: boolean }[] = [
  { value: "price_above",      label: "가격 초과",      needsValue: true },
  { value: "price_below",      label: "가격 미만",      needsValue: true },
  { value: "rsi_above",        label: "RSI 과매수(>)", needsValue: true },
  { value: "rsi_below",        label: "RSI 과매도(<)", needsValue: true },
  { value: "ma_golden_cross",  label: "골든크로스",     needsValue: false },
  { value: "ma_dead_cross",    label: "데드크로스",     needsValue: false },
];

export function AlertPanel() {
  const { conditions, toasts, addAlert, removeAlert } = useAlerts();
  const { data: history = [] } = useSWR<AlertEvent[]>(
    "/api/alerts/events", alertsApi.events, { refreshInterval: 30_000 }
  );

  const [ticker, setTicker] = useState("");
  const [condType, setCondType] = useState<AlertConditionType>("price_above");
  const [condValue, setCondValue] = useState("");
  const [adding, setAdding] = useState(false);

  const selectedOpt = CONDITION_OPTIONS.find((o) => o.value === condType)!;

  async function handleAdd() {
    if (!ticker.trim()) return;
    setAdding(true);
    try {
      await addAlert({
        ticker: ticker.trim().toUpperCase(),
        condition_type: condType,
        condition_value: selectedOpt.needsValue ? parseFloat(condValue) : null,
      });
      setTicker("");
      setCondValue("");
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      {/* 토스트 알림 */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id}
            className="bg-[var(--color-bg-secondary)] border border-[var(--color-primary)] px-3 py-2 text-[10px] font-mono text-[var(--color-text-primary)] shadow-lg animate-in slide-in-from-right-2"
          >
            🔔 {t.message}
          </div>
        ))}
      </div>

      <div className="flex flex-col h-full overflow-hidden text-[10px] font-mono">
        {/* 헤더 */}
        <div className="px-3 py-1.5 text-[9px] uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
          ALERTS
        </div>

        <div className="flex-1 overflow-auto p-3 flex flex-col gap-4">
          {/* 추가 폼 */}
          <div className="flex flex-col gap-1.5">
            <p className="text-[9px] uppercase tracking-widest text-[var(--color-text-secondary)]">NEW CONDITION</p>
            <div className="flex gap-1">
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="w-16 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1.5 py-1 text-[10px] font-mono text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
              />
              <select
                value={condType}
                onChange={(e) => setCondType(e.target.value as AlertConditionType)}
                className="flex-1 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1 py-1 text-[10px] font-mono text-[var(--color-text-primary)] outline-none"
              >
                {CONDITION_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            {selectedOpt.needsValue && (
              <input
                value={condValue}
                onChange={(e) => setCondValue(e.target.value)}
                placeholder="값 입력"
                type="number"
                className="w-full bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] px-1.5 py-1 text-[10px] font-mono text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
              />
            )}
            <button
              onClick={handleAdd}
              disabled={adding || !ticker.trim()}
              className="w-full py-1 border border-[var(--color-primary)] text-[var(--color-primary)] text-[9px] uppercase tracking-widest hover:bg-[var(--color-primary)]/10 disabled:opacity-40 transition-colors"
            >
              {adding ? "추가 중…" : "+ 추가"}
            </button>
          </div>

          {/* 활성 조건 */}
          <div>
            <p className="text-[9px] uppercase tracking-widest text-[var(--color-text-secondary)] mb-1.5">ACTIVE</p>
            {conditions.length === 0 ? (
              <p className="text-[var(--color-text-muted)]">조건 없음</p>
            ) : (
              <div className="flex flex-col gap-1">
                {conditions.map((c) => (
                  <div key={c.id} className="flex items-center justify-between border border-[var(--color-border)] px-2 py-1">
                    <span className="text-[var(--color-text-primary)]">
                      {c.ticker}{" "}
                      <span className="text-[var(--color-text-secondary)]">
                        {CONDITION_OPTIONS.find((o) => o.value === c.condition_type)?.label}
                        {c.condition_value != null ? ` ${c.condition_value}` : ""}
                      </span>
                    </span>
                    <button
                      onClick={() => removeAlert(c.id)}
                      className="text-[#ff453a] hover:opacity-70 transition-opacity ml-2"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 알림 히스토리 */}
          <div>
            <p className="text-[9px] uppercase tracking-widest text-[var(--color-text-secondary)] mb-1.5">HISTORY</p>
            {history.length === 0 ? (
              <p className="text-[var(--color-text-muted)]">내역 없음</p>
            ) : (
              <div className="flex flex-col gap-1">
                {history.slice(0, 20).map((ev) => (
                  <div key={ev.id} className="flex items-start gap-2 border-b border-[var(--color-border)] pb-1">
                    <span className="text-[var(--color-text-muted)] shrink-0">
                      {new Date(ev.triggered_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className="text-[var(--color-text-secondary)]">{formatConditionMsg(ev)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 3: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit
```

Expected: 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/hooks/useAlerts.ts frontend/components/terminal/widgets/AlertPanel.tsx
git commit -m "feat(M7): useAlerts 훅 + AlertPanel 위젯"
```

---

## Task 9: WidgetRegistry + CommandPalette 등록

**Files:**
- Modify: `frontend/components/terminal/WidgetRegistry.ts`

- [ ] **Step 1: WidgetRegistry에 AlertPanel 등록**

`frontend/components/terminal/WidgetRegistry.ts` 수정:

```typescript
import type { ComponentType } from "react";
import { PortfolioWidget } from "./widgets/Portfolio";
import { WatchlistWidget } from "./widgets/Watchlist";
import { ScreenerWidget } from "./widgets/Screener";
import { BacktestWidget } from "./widgets/Backtest";
import { AlertPanel } from "./widgets/AlertPanel";   // 추가

export interface WidgetMeta {
  label: string;
  component: ComponentType;
  defaultW: number;
  defaultH: number;
}

export const WIDGET_REGISTRY: Record<string, WidgetMeta> = {
  portfolio: { label: "포트폴리오", component: PortfolioWidget, defaultW: 12, defaultH: 10 },
  watchlist: { label: "워치리스트", component: WatchlistWidget, defaultW: 6,  defaultH: 8  },
  screener:  { label: "종목분석",   component: ScreenerWidget,  defaultW: 6,  defaultH: 8  },
  backtest:  { label: "백테스트",   component: BacktestWidget,  defaultW: 6,  defaultH: 6  },
  alerts:    { label: "알림 패널",  component: AlertPanel,      defaultW: 4,  defaultH: 8  }, // 추가
};
```

- [ ] **Step 2: 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit && npm run build 2>&1 | tail -10
```

Expected: `✓ Compiled successfully`

- [ ] **Step 3: 전체 pytest 재확인**

```bash
cd /Users/user/Development/private/dudunomics && uv run pytest tests/ -q
```

Expected: 모든 테스트 통과

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/terminal/WidgetRegistry.ts
git commit -m "feat(M7): AlertPanel 위젯 레지스트리 등록 — Cmd+K에서 추가 가능"
```

---

## 완료 기준 검증

서버 실행 후 아래를 순서대로 확인한다.

```bash
# 서버 시작 (별도 터미널)
uv run uvicorn api.main:app --reload --port 8000

# 1. 지표 API 확인
curl -s "http://localhost:8000/api/candles?ticker=AAPL&period=3M&indicators=true" \
  -H "Cookie: access_token=<토큰>" | python3 -m json.tool | grep -A3 '"ma"'

# 2. 알림 생성
curl -s -X POST "http://localhost:8000/api/alerts" \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=<토큰>" \
  -d '{"ticker":"AAPL","condition_type":"price_above","condition_value":1}' | python3 -m json.tool
```

브라우저 확인 (`http://localhost:3333`):
1. `/terminal` → 차트 위젯에서 `[지표]` 버튼 ON → 4구역 지표 표시
2. Cmd+K → "알림 패널 추가" → AlertPanel 위젯 배치
3. AlertPanel에서 `AAPL / 가격 초과 / 1` 등록 → 1분 후 히스토리에 이벤트 표시
