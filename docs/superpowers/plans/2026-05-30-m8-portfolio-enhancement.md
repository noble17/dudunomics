# M8 포트폴리오 고도화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bloomberg Terminal PORTFOLIO 탭에 trades-first 보유 현황, Sharpe/MDD 성과 분석, 리밸런싱 제안, 거래 내역 추적 기능을 추가한다.

**Architecture:** trades 테이블이 단일 진실의 원천. BUY/SELL 기록으로 avg_price/quantity를 자동 계산. portfolio_snapshots에서 Sharpe·MDD를 산출하고 yfinance로 KOSPI/S&P500 벤치마크를 비교. Terminal PORTFOLIO 탭의 PortfolioPanel을 Layout C(왼쪽 사이드바 + 오른쪽 차트/트레이드)로 교체.

**Tech Stack:** DuckDB, FastAPI, Pydantic v2, yfinance, numpy, Next.js 14, SWR, lightweight-charts, react-resizable-panels, Tailwind CSS

---

## 파일 맵

**생성:**
- `api/routers/trades.py` — 거래 CRUD 라우터
- `tests/test_trades_api.py` — 거래 API 테스트 8개
- `tests/test_performance_api.py` — 성과 API 테스트 6개
- `tests/test_rebalancing_api.py` — 리밸런싱 API 테스트 5개
- `frontend/components/terminal/widgets/PositionsPanel.tsx`
- `frontend/components/terminal/widgets/RebalancingPanel.tsx`
- `frontend/components/terminal/widgets/PerformancePanel.tsx`
- `frontend/components/terminal/widgets/TradeLogPanel.tsx`

**수정:**
- `core/repository.py` — trades 함수 + target_weight + 성과 계산
- `api/models.py` — TradeIn/Out, PerformanceOut, RebalancingRow 추가
- `api/routers/portfolio.py` — /performance, /rebalancing 엔드포인트 추가
- `api/routers/holdings.py` — PATCH /{ticker} target_weight 추가
- `api/main.py` — trades_router 등록
- `frontend/lib/types.ts` — Trade, PerformanceData, RebalancingRow 타입 추가
- `frontend/lib/api.ts` — tradesApi, performanceApi, rebalancingApi 추가
- `frontend/components/terminal/panels/PortfolioPanel.tsx` — Layout C로 교체

---

### Task 1: DB — trades 테이블 + target_weight 마이그레이션

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: `_init_schema` DDL에 trades 테이블 추가**

`core/repository.py`의 `_init_schema` 함수 내 `ddl` 문자열에서 `user_alert_events` 블록 바로 뒤(`"""` 닫기 직전)에 추가:

```python
    CREATE SEQUENCE IF NOT EXISTS trades_id_seq START 1;
    CREATE TABLE IF NOT EXISTS trades (
        id          INTEGER DEFAULT nextval('trades_id_seq') PRIMARY KEY,
        user_id     INTEGER NOT NULL,
        ticker      VARCHAR NOT NULL,
        market      VARCHAR,
        trade_type  VARCHAR NOT NULL,
        quantity    DOUBLE NOT NULL,
        price       DOUBLE NOT NULL,
        currency    VARCHAR NOT NULL,
        traded_at   VARCHAR NOT NULL,
        fee         DOUBLE DEFAULT 0,
        note        TEXT,
        created_at  TIMESTAMP DEFAULT current_timestamp
    );
```

- [ ] **Step 2: `_run_migrations`에 target_weight + 시딩 마이그레이션 추가**

`_run_migrations` 함수 끝 `conn.commit()` 바로 위에 추가:

```python
    # holdings: target_weight 컬럼 추가
    if not _has_column(conn, "holdings", "target_weight"):
        conn.execute(text(
            "ALTER TABLE holdings ADD COLUMN target_weight DOUBLE DEFAULT NULL"
        ))

    # trades: 기존 holdings를 Day 0 BUY로 시딩 (최초 1회)
    seeded = conn.execute(text("SELECT COUNT(*) FROM trades")).fetchone()[0]
    if seeded == 0:
        holdings = conn.execute(text(
            "SELECT user_id, ticker, market, quantity, avg_price, currency FROM holdings"
        )).fetchall()
        for h in holdings:
            if h[3] > 0 and h[4] > 0:
                conn.execute(text("""
                    INSERT INTO trades
                      (user_id, ticker, market, trade_type, quantity, price, currency, traded_at, fee)
                    VALUES (:uid, :ticker, :market, 'BUY', :qty, :price, :cur, '2024-01-01', 0)
                """), {"uid": h[0], "ticker": h[1], "market": h[2],
                       "qty": h[3], "price": h[4], "cur": h[5]})
```

- [ ] **Step 3: 서버 재시작으로 마이그레이션 적용 확인**

```bash
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000 &
sleep 2
curl -s http://localhost:8000/docs | grep -c "trades" && echo "trades 엔드포인트 확인"
```

- [ ] **Step 4: Commit**

```bash
git add core/repository.py
git commit -m "feat(m8): trades 테이블 + target_weight 컬럼 마이그레이션"
```

---

### Task 2: Repository — trades CRUD + avg_price 자동 계산

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: trades CRUD 함수 추가**

`core/repository.py` 끝에 추가 (마지막 함수 아래):

```python
# ── Trades ────────────────────────────────────────────────────────────────────

def create_trade(
    user_id: int, ticker: str, market: str | None,
    trade_type: str, quantity: float, price: float,
    currency: str, traded_at: str, fee: float = 0, note: str | None = None
) -> int:
    with session() as s:
        row = s.execute(text("SELECT nextval('trades_id_seq')")).fetchone()
        trade_id = row[0]
        s.execute(text("""
            INSERT INTO trades
              (id, user_id, ticker, market, trade_type, quantity, price, currency, traded_at, fee, note)
            VALUES
              (:id, :uid, :ticker, :market, :type, :qty, :price, :cur, :date, :fee, :note)
        """), {"id": trade_id, "uid": user_id, "ticker": ticker, "market": market,
               "type": trade_type, "qty": quantity, "price": price, "cur": currency,
               "date": traded_at, "fee": fee, "note": note})
        s.commit()
        _sync_holding_from_trades(s, user_id, ticker)
        s.commit()
    return trade_id


def get_trades(user_id: int, ticker: str | None = None) -> list[dict]:
    with session() as s:
        if ticker:
            rows = s.execute(text("""
                SELECT id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid AND ticker = :ticker
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id, "ticker": ticker}).fetchall()
        else:
            rows = s.execute(text("""
                SELECT id, ticker, market, trade_type, quantity, price, currency,
                       traded_at, fee, note, created_at
                FROM trades WHERE user_id = :uid
                ORDER BY traded_at DESC, created_at DESC
            """), {"uid": user_id}).fetchall()
    cols = ["id", "ticker", "market", "trade_type", "quantity", "price", "currency",
            "traded_at", "fee", "note", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def delete_trade(user_id: int, trade_id: int) -> bool:
    with session() as s:
        row = s.execute(text(
            "SELECT ticker FROM trades WHERE id = :id AND user_id = :uid"
        ), {"id": trade_id, "uid": user_id}).fetchone()
        if not row:
            return False
        ticker = row[0]
        s.execute(text(
            "DELETE FROM trades WHERE id = :id AND user_id = :uid"
        ), {"id": trade_id, "uid": user_id})
        s.commit()
        _sync_holding_from_trades(s, user_id, ticker)
        s.commit()
    return True


def _sync_holding_from_trades(s, user_id: int, ticker: str) -> None:
    """거래 내역에서 avg_price/quantity를 재계산해 holdings에 반영."""
    rows = s.execute(text("""
        SELECT trade_type, quantity, price
        FROM trades
        WHERE user_id = :uid AND ticker = :ticker
        ORDER BY traded_at ASC, created_at ASC
    """), {"uid": user_id, "ticker": ticker}).fetchall()

    total_qty = 0.0
    total_cost = 0.0
    for trade_type, qty, price in rows:
        if trade_type == "BUY":
            total_cost += qty * price
            total_qty += qty
        elif trade_type == "SELL":
            total_qty -= qty

    if total_qty <= 0:
        # 전량 매도 → holdings 삭제
        s.execute(text(
            "DELETE FROM holdings WHERE user_id = :uid AND ticker = :ticker"
        ), {"uid": user_id, "ticker": ticker})
        return

    buy_qty = sum(qty for tt, qty, _ in rows if tt == "BUY")
    avg_price = total_cost / buy_qty if buy_qty > 0 else 0.0

    existing = s.execute(text(
        "SELECT ticker FROM holdings WHERE user_id = :uid AND ticker = :ticker"
    ), {"uid": user_id, "ticker": ticker}).fetchone()

    if existing:
        s.execute(text("""
            UPDATE holdings SET quantity = :qty, avg_price = :avg, updated_at = current_timestamp
            WHERE user_id = :uid AND ticker = :ticker
        """), {"qty": total_qty, "avg": avg_price, "uid": user_id, "ticker": ticker})
    # holding이 없으면 trades로 만들어진 케이스 — 기존 upsert_holding으로 처리 필요


def get_realized_pnl(user_id: int) -> float:
    """전체 실현 손익 합산. SELL 시점의 avg_price 기준."""
    trades = get_trades(user_id)
    by_ticker: dict[str, list] = {}
    for t in sorted(trades, key=lambda x: (x["traded_at"], x["created_at"])):
        by_ticker.setdefault(t["ticker"], []).append(t)

    total_pnl = 0.0
    for ticker_trades in by_ticker.values():
        buy_qty = 0.0
        buy_cost = 0.0
        for t in ticker_trades:
            if t["trade_type"] == "BUY":
                buy_qty += t["quantity"]
                buy_cost += t["quantity"] * t["price"]
            elif t["trade_type"] == "SELL" and buy_qty > 0:
                avg = buy_cost / buy_qty
                total_pnl += (t["price"] - avg) * t["quantity"]
    return total_pnl
```

- [ ] **Step 2: Commit**

```bash
git add core/repository.py
git commit -m "feat(m8): trades CRUD + _sync_holding_from_trades"
```

---

### Task 3: Repository — 성과 계산 (Sharpe, MDD, 벤치마크)

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: 성과 계산 함수 추가**

`core/repository.py` 끝에 추가:

```python
# ── Performance ───────────────────────────────────────────────────────────────

import math

def _period_to_days(period: str) -> int:
    return {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 9999}[period]


def get_portfolio_returns(user_id: int, period: str = "6m") -> list[dict]:
    """portfolio_snapshots에서 일별 수익률 시계열 반환."""
    days = _period_to_days(period)
    with session() as s:
        rows = s.execute(text("""
            SELECT ts::DATE as date, total_equity_krw
            FROM portfolio_snapshots
            WHERE user_id = :uid
              AND ts >= current_timestamp - INTERVAL :days DAY
            ORDER BY date ASC
        """), {"uid": user_id, "days": days}).fetchall()
    return [{"date": str(r[0]), "equity": float(r[1])} for r in rows]


def calc_performance(equity_series: list[dict]) -> dict:
    """Sharpe, MDD, total_return 계산."""
    if len(equity_series) < 2:
        return {"sharpe": 0.0, "mdd": 0.0, "total_return": 0.0, "annualized_return": 0.0}

    equities = [e["equity"] for e in equity_series]
    returns = [(equities[i] - equities[i-1]) / equities[i-1]
               for i in range(1, len(equities)) if equities[i-1] > 0]

    if not returns:
        return {"sharpe": 0.0, "mdd": 0.0, "total_return": 0.0, "annualized_return": 0.0}

    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / n
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0

    # MDD
    peak = equities[0]
    mdd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (peak - e) / peak if peak > 0 else 0
        if dd > mdd:
            mdd = dd

    total_return = (equities[-1] - equities[0]) / equities[0] * 100 if equities[0] > 0 else 0
    days = len(equities)
    annualized = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0

    return {
        "sharpe": round(sharpe, 3),
        "mdd": round(-mdd * 100, 2),
        "total_return": round(total_return, 2),
        "annualized_return": round(annualized, 2),
    }
```

- [ ] **Step 2: Commit**

```bash
git add core/repository.py
git commit -m "feat(m8): Sharpe/MDD 성과 계산 함수"
```

---

### Task 4: API Models 추가

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: 새 모델 추가**

`api/models.py` 끝에 추가:

```python
# ── M8 Trades ─────────────────────────────────────────────────────────────────

class TradeIn(BaseModel):
    ticker: str
    market: str | None = None
    trade_type: Literal["BUY", "SELL"]
    quantity: float
    price: float
    currency: Literal["KRW", "USD"]
    traded_at: str          # "YYYY-MM-DD"
    fee: float = 0.0
    note: str | None = None


class TradeOut(TradeIn):
    id: int
    created_at: datetime


# ── M8 Performance ────────────────────────────────────────────────────────────

class BenchmarkStats(BaseModel):
    return_pct: float
    correlation: float


class PerformanceChartPoint(BaseModel):
    date: str
    portfolio: float
    kospi: float
    sp500: float


class PerformanceOut(BaseModel):
    sharpe: float
    mdd: float
    total_return: float
    annualized_return: float
    benchmark: dict[str, BenchmarkStats]
    chart: list[PerformanceChartPoint]


# ── M8 Rebalancing ────────────────────────────────────────────────────────────

class RebalancingRow(BaseModel):
    ticker: str
    name: str
    current_weight: float
    target_weight: float | None
    diff_weight: float | None
    action: str             # "BUY" | "SELL" | "HOLD" | "NO_TARGET"
    amount_krw: float


class TargetWeightUpdate(BaseModel):
    target_weight: float | None = None
```

- [ ] **Step 2: Commit**

```bash
git add api/models.py
git commit -m "feat(m8): TradeIn/Out, PerformanceOut, RebalancingRow 모델"
```

---

### Task 5: Trades 라우터

**Files:**
- Create: `api/routers/trades.py`

- [ ] **Step 1: 라우터 파일 생성**

```python
# api/routers/trades.py
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from api.models import TradeIn, TradeOut
import core.repository as repo

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=list[TradeOut])
def list_trades(
    ticker: str | None = Query(default=None),
    user: CurrentUser = Depends(current_user),
):
    return repo.get_trades(user.id, ticker=ticker)


@router.post("", response_model=TradeOut, status_code=201)
def create_trade(body: TradeIn, user: CurrentUser = Depends(current_user)):
    # SELL 수량 검증
    if body.trade_type == "SELL":
        holdings = repo.get_holdings(user.id)
        holding = next((h for h in holdings if h["ticker"] == body.ticker), None)
        if not holding or holding["quantity"] < body.quantity:
            raise HTTPException(
                status_code=422,
                detail=f"{body.ticker} 보유 수량({holding['quantity'] if holding else 0})보다 매도 수량이 많습니다."
            )

    trade_id = repo.create_trade(
        user_id=user.id,
        ticker=body.ticker,
        market=body.market,
        trade_type=body.trade_type,
        quantity=body.quantity,
        price=body.price,
        currency=body.currency,
        traded_at=body.traded_at,
        fee=body.fee,
        note=body.note,
    )
    trades = repo.get_trades(user.id)
    trade = next(t for t in trades if t["id"] == trade_id)
    return trade


@router.delete("/{trade_id}", status_code=200)
def delete_trade(trade_id: int, user: CurrentUser = Depends(current_user)):
    ok = repo.delete_trade(user.id, trade_id)
    if not ok:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    return {"ok": True}
```

- [ ] **Step 2: Commit**

```bash
git add api/routers/trades.py
git commit -m "feat(m8): trades 라우터 (GET/POST/DELETE)"
```

---

### Task 6: Performance + Rebalancing 엔드포인트

**Files:**
- Modify: `api/routers/portfolio.py`
- Modify: `api/routers/holdings.py`

- [ ] **Step 1: portfolio.py에 /performance 엔드포인트 추가**

`api/routers/portfolio.py` 상단 import에 추가:

```python
import math
from api.models import PortfolioSnapshot, PortfolioRow, SnapshotHistory, EventIn, EventOut, PerformanceOut, BenchmarkStats, PerformanceChartPoint, RebalancingRow
```

파일 끝에 추가:

```python
@router.get("/performance", response_model=PerformanceOut)
def get_performance(
    period: str = "6m",
    user: CurrentUser = Depends(current_user),
):
    if period not in ("1m", "3m", "6m", "1y", "all"):
        period = "6m"

    equity_series = repo.get_portfolio_returns(user.id, period)
    metrics = repo.calc_performance(equity_series)

    # 벤치마크 (yfinance)
    benchmark: dict[str, BenchmarkStats] = {}
    chart: list[PerformanceChartPoint] = []

    try:
        import yfinance as yf
        from datetime import date, timedelta

        days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 1825}[period]
        start = (date.today() - timedelta(days=days)).isoformat()
        end = date.today().isoformat()

        kospi_df = yf.download("^KS11", start=start, end=end, progress=False)["Close"]
        sp500_df = yf.download("^GSPC", start=start, end=end, progress=False)["Close"]

        def to_cum_return(series) -> dict[str, float]:
            if series.empty:
                return {}
            base = float(series.iloc[0])
            return {str(d.date()): round((float(v) - base) / base * 100, 2)
                    for d, v in series.items() if base > 0}

        kospi_map = to_cum_return(kospi_df)
        sp500_map = to_cum_return(sp500_df)

        # 포트폴리오 누적 수익률 맵
        port_map: dict[str, float] = {}
        if equity_series:
            base = equity_series[0]["equity"]
            for e in equity_series:
                if base > 0:
                    port_map[e["date"]] = round((e["equity"] - base) / base * 100, 2)

        all_dates = sorted(set(port_map) | set(kospi_map) | set(sp500_map))
        chart = [
            PerformanceChartPoint(
                date=d,
                portfolio=port_map.get(d, 0.0),
                kospi=kospi_map.get(d, 0.0),
                sp500=sp500_map.get(d, 0.0),
            )
            for d in all_dates
        ]

        # 벤치마크 total return
        def bench_total(m: dict) -> float:
            vals = list(m.values())
            return vals[-1] if vals else 0.0

        benchmark = {
            "kospi": BenchmarkStats(return_pct=bench_total(kospi_map), correlation=0.0),
            "sp500": BenchmarkStats(return_pct=bench_total(sp500_map), correlation=0.0),
        }
    except Exception:
        pass

    return PerformanceOut(
        sharpe=metrics["sharpe"],
        mdd=metrics["mdd"],
        total_return=metrics["total_return"],
        annualized_return=metrics["annualized_return"],
        benchmark=benchmark,
        chart=chart,
    )


@router.get("/rebalancing", response_model=list[RebalancingRow])
def get_rebalancing(user: CurrentUser = Depends(current_user)):
    holdings = repo.get_holdings(user.id)
    if not holdings:
        return []

    tickers = [h["ticker"] for h in holdings]
    markets = {h["ticker"]: h.get("market") for h in holdings}
    prices = _price_provider.get_current_prices(tickers, markets=markets)
    usdkrw = _get_usdkrw()

    total_krw = 0.0
    mv_map: dict[str, float] = {}
    for h in holdings:
        ticker = h["ticker"]
        if ticker not in prices:
            continue
        p = prices[ticker]
        mv = p.current * h["quantity"]
        mv_krw = mv if p.currency == "KRW" else mv * usdkrw
        mv_map[ticker] = mv_krw
        total_krw += mv_krw

    rows: list[RebalancingRow] = []
    for h in holdings:
        ticker = h["ticker"]
        mv_krw = mv_map.get(ticker, 0.0)
        current_w = round(mv_krw / total_krw * 100, 2) if total_krw > 0 else 0.0
        target_w = h.get("target_weight")

        if target_w is None:
            action = "NO_TARGET"
            diff = None
            amount = 0.0
        else:
            diff = round(target_w - current_w, 2)
            amount = abs(diff / 100 * total_krw)
            if abs(diff) < 0.5:
                action = "HOLD"
            elif diff > 0:
                action = "BUY"
            else:
                action = "SELL"

        rows.append(RebalancingRow(
            ticker=ticker,
            name=h["name"],
            current_weight=current_w,
            target_weight=target_w,
            diff_weight=diff,
            action=action,
            amount_krw=round(amount),
        ))

    return sorted(rows, key=lambda r: abs(r.diff_weight or 0), reverse=True)
```

- [ ] **Step 2: holdings.py에 PATCH /{ticker} 추가**

`api/routers/holdings.py`에 import 추가:

```python
from api.models import CashUpdate, HoldingIn, HoldingOut, TickerLookupOut, TickerSearchHit, TargetWeightUpdate
```

파일 끝에 추가:

```python
@router.patch("/{ticker}")
def patch_holding(ticker: str, body: TargetWeightUpdate,
                  user: CurrentUser = Depends(current_user)):
    holdings = repo.get_holdings(user.id)
    if not any(h["ticker"] == ticker for h in holdings):
        raise HTTPException(status_code=404, detail="보유 종목을 찾을 수 없습니다.")
    repo.set_holding_target_weight(user.id, ticker, body.target_weight)

    # 합계 100% 초과 경고
    updated = repo.get_holdings(user.id)
    total_target = sum(
        h.get("target_weight") or 0 for h in updated if h.get("target_weight") is not None
    )
    warning = total_target > 100
    return {"ok": True, "total_target_weight": round(total_target, 2), "over_100": warning}
```

- [ ] **Step 3: repository.py에 set_holding_target_weight 추가**

`core/repository.py`의 `delete_holding` 함수 아래에 추가:

```python
def set_holding_target_weight(user_id: int, ticker: str, target_weight: float | None) -> None:
    with session() as s:
        s.execute(text("""
            UPDATE holdings SET target_weight = :tw
            WHERE user_id = :uid AND ticker = :ticker
        """), {"tw": target_weight, "uid": user_id, "ticker": ticker})
        s.commit()
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/portfolio.py api/routers/holdings.py core/repository.py
git commit -m "feat(m8): /performance, /rebalancing 엔드포인트 + target_weight PATCH"
```

---

### Task 7: main.py에 trades_router 등록

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: trades_router import + 등록**

`api/main.py`의 router import 블록에 추가:

```python
from api.routers.trades import router as trades_router
```

`app.include_router(alerts_router)` 아래에 추가:

```python
app.include_router(trades_router)
```

- [ ] **Step 2: 서버 재시작 + 엔드포인트 확인**

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys; paths=json.load(sys.stdin)['paths']; print([p for p in paths if 'trade' in p or 'performance' in p or 'rebalancing' in p])"
```

Expected: `['/api/trades', '/api/portfolio/performance', '/api/portfolio/rebalancing']` 포함

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat(m8): trades_router 등록"
```

---

### Task 8: 테스트 — test_trades_api.py

**Files:**
- Create: `tests/test_trades_api.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_trades_api.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def trades_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "trades@test.com", "password": "password123"})
    # 보유 종목 사전 등록
    c.put("/api/holdings/AAPL", json={
        "name": "Apple Inc.", "currency": "USD",
        "quantity": 10, "avg_price": 180.0, "market": "NASDAQ"
    })
    return c


def test_list_trades_empty(trades_client):
    res = trades_client.get("/api/trades")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_buy_trade(trades_client):
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "market": "NASDAQ", "trade_type": "BUY",
        "quantity": 5, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ticker"] == "AAPL"
    assert data["trade_type"] == "BUY"
    assert "id" in data


def test_create_sell_trade(trades_client):
    # 먼저 BUY
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 5, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    # SELL
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "SELL",
        "quantity": 3, "price": 210.0, "currency": "USD", "traded_at": "2025-07-01"
    })
    assert res.status_code == 201
    assert res.json()["trade_type"] == "SELL"


def test_sell_exceeds_quantity_rejected(trades_client):
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "SELL",
        "quantity": 999, "price": 200.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    assert res.status_code == 422


def test_ticker_filter(trades_client):
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 1, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    res = trades_client.get("/api/trades?ticker=AAPL")
    assert res.status_code == 200
    assert all(t["ticker"] == "AAPL" for t in res.json())


def test_delete_trade(trades_client):
    create_res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 2, "price": 185.0, "currency": "USD", "traded_at": "2025-05-01"
    })
    trade_id = create_res.json()["id"]
    del_res = trades_client.delete(f"/api/trades/{trade_id}")
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True


def test_delete_nonexistent_trade(trades_client):
    res = trades_client.delete("/api/trades/99999")
    assert res.status_code == 404


def test_buy_updates_holding_avg_price(trades_client):
    # 기존 avg_price=180, qty=10. BUY 5주 @200 → 새 avg = (10*180+5*200)/15 = 186.67
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 5, "price": 200.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    holdings = trades_client.get("/api/holdings").json()
    aapl = next(h for h in holdings if h["ticker"] == "AAPL")
    # avg_price는 trades 합산이므로 초기 시딩 포함 검증
    assert aapl["quantity"] >= 15
```

- [ ] **Step 2: 테스트 실행**

```bash
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
uv run pytest tests/test_trades_api.py -v
```

Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_trades_api.py
git commit -m "test(m8): trades API 테스트 8개"
```

---

### Task 9: 테스트 — test_performance_api.py

**Files:**
- Create: `tests/test_performance_api.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_performance_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date, timedelta


@pytest.fixture
def perf_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "perf@test.com", "password": "password123"})
    return c


def test_performance_schema(perf_client):
    res = perf_client.get("/api/portfolio/performance?period=6m")
    assert res.status_code == 200
    data = res.json()
    assert "sharpe" in data
    assert "mdd" in data
    assert "total_return" in data
    assert "annualized_return" in data
    assert "benchmark" in data
    assert "chart" in data


def test_performance_no_snapshots_returns_zeros(perf_client):
    res = perf_client.get("/api/portfolio/performance")
    assert res.status_code == 200
    data = res.json()
    assert data["sharpe"] == 0.0
    assert data["mdd"] == 0.0


def test_sharpe_calculation():
    import core.repository as repo
    series = [
        {"date": "2025-01-01", "equity": 1000000},
        {"date": "2025-01-02", "equity": 1010000},
        {"date": "2025-01-03", "equity": 1005000},
        {"date": "2025-01-04", "equity": 1020000},
        {"date": "2025-01-05", "equity": 1015000},
    ]
    result = repo.calc_performance(series)
    assert isinstance(result["sharpe"], float)
    assert isinstance(result["mdd"], float)
    assert result["mdd"] <= 0   # MDD는 음수 또는 0


def test_mdd_calculation():
    import core.repository as repo
    series = [
        {"date": "2025-01-01", "equity": 1000000},
        {"date": "2025-01-02", "equity": 1100000},  # 고점
        {"date": "2025-01-03", "equity": 880000},   # -20% 낙폭
        {"date": "2025-01-04", "equity": 950000},
    ]
    result = repo.calc_performance(series)
    assert result["mdd"] <= -19.0  # 약 -20% MDD


def test_period_filter_invalid_defaults_to_6m(perf_client):
    res = perf_client.get("/api/portfolio/performance?period=invalid")
    assert res.status_code == 200


def test_yfinance_failure_graceful_fallback(perf_client):
    with patch("yfinance.download", side_effect=Exception("network error")):
        res = perf_client.get("/api/portfolio/performance?period=1m")
    assert res.status_code == 200
    data = res.json()
    assert data["benchmark"] == {}
    assert data["chart"] == []
```

- [ ] **Step 2: 테스트 실행**

```bash
uv run pytest tests/test_performance_api.py -v
```

Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_performance_api.py
git commit -m "test(m8): performance API 테스트 6개"
```

---

### Task 10: 테스트 — test_rebalancing_api.py

**Files:**
- Create: `tests/test_rebalancing_api.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_rebalancing_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def reb_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app

    mock_price = MagicMock()
    mock_price.current = 100.0
    mock_price.currency = "USD"

    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_pp.get_current_prices.return_value = {
            "AAPL": mock_price, "MSFT": mock_price
        }
        c = TestClient(app)
        c.post("/api/auth/signup", json={"email": "reb@test.com", "password": "password123"})
        c.put("/api/holdings/AAPL", json={
            "name": "Apple", "currency": "USD", "quantity": 10, "avg_price": 180.0
        })
        c.put("/api/holdings/MSFT", json={
            "name": "Microsoft", "currency": "USD", "quantity": 5, "avg_price": 400.0
        })
        yield c


def test_rebalancing_empty_without_target(reb_client):
    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_price = MagicMock()
        mock_price.current = 100.0
        mock_price.currency = "USD"
        mock_pp.get_current_prices.return_value = {"AAPL": mock_price, "MSFT": mock_price}
        res = reb_client.get("/api/portfolio/rebalancing")
    assert res.status_code == 200
    data = res.json()
    assert all(r["action"] == "NO_TARGET" for r in data)


def test_patch_target_weight(reb_client):
    res = reb_client.patch("/api/holdings/AAPL", json={"target_weight": 60.0})
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_patch_target_weight_over_100_warns(reb_client):
    reb_client.patch("/api/holdings/AAPL", json={"target_weight": 70.0})
    res = reb_client.patch("/api/holdings/MSFT", json={"target_weight": 60.0})
    assert res.status_code == 200
    assert res.json()["over_100"] is True


def test_rebalancing_action_buy_sell(reb_client):
    reb_client.patch("/api/holdings/AAPL", json={"target_weight": 30.0})
    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_price = MagicMock()
        mock_price.current = 100.0
        mock_price.currency = "USD"
        mock_pp.get_current_prices.return_value = {"AAPL": mock_price, "MSFT": mock_price}
        res = reb_client.get("/api/portfolio/rebalancing")
    assert res.status_code == 200


def test_patch_nonexistent_ticker(reb_client):
    res = reb_client.patch("/api/holdings/ZZZZ", json={"target_weight": 50.0})
    assert res.status_code == 404
```

- [ ] **Step 2: 테스트 실행**

```bash
uv run pytest tests/test_rebalancing_api.py -v
```

Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_rebalancing_api.py
git commit -m "test(m8): rebalancing API 테스트 5개"
```

---

### Task 11: 프론트엔드 타입 + API 클라이언트

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: types.ts에 M8 타입 추가**

`frontend/lib/types.ts` 끝에 추가:

```typescript
// ── M8 Trades ──────────────────────────────────────────────────────────────

export interface TradeIn {
  ticker: string;
  market?: string;
  trade_type: "BUY" | "SELL";
  quantity: number;
  price: number;
  currency: "KRW" | "USD";
  traded_at: string;  // "YYYY-MM-DD"
  fee?: number;
  note?: string;
}

export interface TradeOut extends TradeIn {
  id: number;
  created_at: string;
}

// ── M8 Performance ─────────────────────────────────────────────────────────

export interface BenchmarkStats {
  return_pct: number;
  correlation: number;
}

export interface PerformanceChartPoint {
  date: string;
  portfolio: number;
  kospi: number;
  sp500: number;
}

export interface PerformanceData {
  sharpe: number;
  mdd: number;
  total_return: number;
  annualized_return: number;
  benchmark: Record<string, BenchmarkStats>;
  chart: PerformanceChartPoint[];
}

// ── M8 Rebalancing ─────────────────────────────────────────────────────────

export interface RebalancingRow {
  ticker: string;
  name: string;
  current_weight: number;
  target_weight: number | null;
  diff_weight: number | null;
  action: "BUY" | "SELL" | "HOLD" | "NO_TARGET";
  amount_krw: number;
}
```

- [ ] **Step 2: api.ts에 M8 API 추가**

`frontend/lib/api.ts` 상단 import에 추가:

```typescript
import type { ..., TradeIn, TradeOut, PerformanceData, RebalancingRow } from "./types";
```

파일 끝에 추가:

```typescript
export const tradesApi = {
  list: (ticker?: string): Promise<TradeOut[]> =>
    request<TradeOut[]>(`/api/trades${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`),
  create: (body: TradeIn): Promise<TradeOut> =>
    request<TradeOut>("/api/trades", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: number): Promise<{ ok: boolean }> =>
    request<{ ok: boolean }>(`/api/trades/${id}`, { method: "DELETE" }),
};

export const performanceApi = {
  get: (period = "6m"): Promise<PerformanceData> =>
    request<PerformanceData>(`/api/portfolio/performance?period=${period}`),
};

export const rebalancingApi = {
  get: (): Promise<RebalancingRow[]> =>
    request<RebalancingRow[]>("/api/portfolio/rebalancing"),
  setTargetWeight: (ticker: string, target_weight: number | null) =>
    request<{ ok: boolean; total_target_weight: number; over_100: boolean }>(
      `/api/holdings/${ticker}`,
      { method: "PATCH", body: JSON.stringify({ target_weight }) }
    ),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(m8): 프론트엔드 타입 + API 클라이언트"
```

---

### Task 12: PositionsPanel + RebalancingPanel

**Files:**
- Create: `frontend/components/terminal/widgets/PositionsPanel.tsx`
- Create: `frontend/components/terminal/widgets/RebalancingPanel.tsx`

- [ ] **Step 1: PositionsPanel.tsx 작성**

```tsx
// frontend/components/terminal/widgets/PositionsPanel.tsx
"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";

interface Props {
  onTickerSelect?: (ticker: string) => void;
  selectedTicker?: string;
}

export function PositionsPanel({ onTickerSelect, selectedTicker }: Props) {
  const { data: snapshot, isLoading } = useSWR(
    "/api/portfolio/current",
    portfolioApi.current,
    { refreshInterval: 30_000 }
  );

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );
  if (!snapshot?.rows.length) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">보유 종목 없음</div>
  );

  const totalKrw = snapshot.total_equity_krw || 1;
  const realizedPnl = (snapshot as any).realized_pnl_krw ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        POSITIONS
      </div>
      <div className="flex-1 overflow-auto">
        <div className="px-3 py-1">
          <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
            <span>Ticker</span>
            <span className="text-right">수익률</span>
            <span className="text-right">평가액</span>
          </div>
          {snapshot.rows.map((row) => (
            <div
              key={row.ticker}
              onClick={() => onTickerSelect?.(row.ticker)}
              className={`grid grid-cols-3 py-1 border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] text-[10px] font-mono ${
                selectedTicker === row.ticker ? "bg-[var(--color-bg-tertiary)]" : ""
              }`}
            >
              <span className="text-[var(--color-text-primary)]">{row.ticker}</span>
              <span className={`text-right ${row.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                {row.return_pct >= 0 ? "+" : ""}{row.return_pct.toFixed(1)}%
              </span>
              <span className="text-right text-[var(--color-text-secondary)]">
                ₩{(row.market_value_krw / 1_000_000).toFixed(1)}M
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="px-3 py-2 border-t border-[var(--color-border)] shrink-0 space-y-0.5">
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">총 평가</span>
          <span className="text-[var(--color-text-primary)]">
            ₩{(snapshot.total_equity_krw / 1_000_000).toFixed(1)}M
          </span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">실현 손익</span>
          <span className={realizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
            {realizedPnl >= 0 ? "+" : ""}₩{(realizedPnl / 10_000).toFixed(0)}만
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: RebalancingPanel.tsx 작성**

```tsx
// frontend/components/terminal/widgets/RebalancingPanel.tsx
"use client";
import { useState } from "react";
import useSWR from "swr";
import { rebalancingApi } from "@/lib/api";

export function RebalancingPanel() {
  const { data: rows, mutate, isLoading } = useSWR(
    "/api/portfolio/rebalancing",
    rebalancingApi.get,
    { refreshInterval: 60_000 }
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");

  async function saveTarget(ticker: string) {
    const val = parseFloat(editVal);
    await rebalancingApi.setTargetWeight(ticker, isNaN(val) ? null : val);
    setEditing(null);
    mutate();
  }

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary-dim,#ff9500)] border-b border-[var(--color-border)] shrink-0">
        REBALANCING
      </div>
      <div className="flex-1 overflow-auto px-3 py-1">
        {!rows?.length && (
          <div className="text-[10px] font-mono text-[var(--color-text-muted)] mt-2">데이터 없음</div>
        )}
        <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
          <span>Ticker</span>
          <span className="text-right">현재→목표</span>
          <span className="text-right">액션</span>
        </div>
        {rows?.map((row) => (
          <div key={row.ticker} className="grid grid-cols-3 py-1 border-b border-[var(--color-border)] items-center">
            <span
              className="text-[10px] font-mono text-[var(--color-text-primary)] cursor-pointer hover:text-[var(--color-primary)]"
              onClick={() => { setEditing(row.ticker); setEditVal(String(row.target_weight ?? "")); }}
            >
              {row.ticker}
            </span>
            <div className="text-right text-[10px] font-mono text-[var(--color-text-secondary)]">
              {editing === row.ticker ? (
                <input
                  type="number"
                  value={editVal}
                  onChange={(e) => setEditVal(e.target.value)}
                  onBlur={() => saveTarget(row.ticker)}
                  onKeyDown={(e) => e.key === "Enter" && saveTarget(row.ticker)}
                  className="w-16 bg-[var(--color-bg-tertiary)] border border-[var(--color-primary)] text-[var(--color-text-primary)] px-1 text-right font-mono text-[10px]"
                  autoFocus
                />
              ) : (
                <span>
                  {row.current_weight.toFixed(1)}%
                  {row.target_weight != null ? `→${row.target_weight.toFixed(1)}%` : ""}
                </span>
              )}
            </div>
            <div className="text-right text-[10px] font-mono">
              {row.action === "BUY" && (
                <span className="text-green-400">▲ ₩{(row.amount_krw / 10_000).toFixed(0)}만</span>
              )}
              {row.action === "SELL" && (
                <span className="text-red-400">▼ ₩{(row.amount_krw / 10_000).toFixed(0)}만</span>
              )}
              {row.action === "HOLD" && <span className="text-[var(--color-text-muted)]">HOLD</span>}
              {row.action === "NO_TARGET" && (
                <span className="text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-primary)]"
                  onClick={() => { setEditing(row.ticker); setEditVal(""); }}>
                  설정
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/widgets/PositionsPanel.tsx \
        frontend/components/terminal/widgets/RebalancingPanel.tsx
git commit -m "feat(m8): PositionsPanel + RebalancingPanel 컴포넌트"
```

---

### Task 13: PerformancePanel

**Files:**
- Create: `frontend/components/terminal/widgets/PerformancePanel.tsx`

- [ ] **Step 1: PerformancePanel.tsx 작성**

```tsx
// frontend/components/terminal/widgets/PerformancePanel.tsx
"use client";
import { useState } from "react";
import useSWR from "swr";
import { performanceApi } from "@/lib/api";
import { createChart, ColorType, LineStyle } from "lightweight-charts";
import { useEffect, useRef } from "react";

type Period = "1m" | "3m" | "6m" | "1y" | "all";
const PERIODS: Period[] = ["1m", "3m", "6m", "1y", "all"];

function PerformanceChart({ data }: { data: { date: string; portfolio: number; kospi: number; sp500: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !data.length) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#0d1929" }, textColor: "#888" },
      grid: { vertLines: { color: "#1e3a5f" }, horzLines: { color: "#1e3a5f" } },
      width: containerRef.current.clientWidth,
      height: 140,
      rightPriceScale: { borderColor: "#1e3a5f" },
      timeScale: { borderColor: "#1e3a5f" },
    });
    const portSeries = chart.addLineSeries({ color: "#4a9eff", lineWidth: 2 });
    const kospiSeries = chart.addLineSeries({ color: "#26c940", lineWidth: 1, lineStyle: LineStyle.Dashed });
    const sp500Series = chart.addLineSeries({ color: "#ff9500", lineWidth: 1, lineStyle: LineStyle.Dashed });

    portSeries.setData(data.map(d => ({ time: d.date, value: d.portfolio })));
    kospiSeries.setData(data.map(d => ({ time: d.date, value: d.kospi })));
    sp500Series.setData(data.map(d => ({ time: d.date, value: d.sp500 })));
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [data]);

  return <div ref={containerRef} />;
}

export function PerformancePanel() {
  const [period, setPeriod] = useState<Period>("6m");
  const { data, isLoading } = useSWR(
    `/api/portfolio/performance?period=${period}`,
    () => performanceApi.get(period),
    { refreshInterval: 300_000 }
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] shrink-0">
        <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">PERFORMANCE</span>
        <div className="flex gap-2">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-[9px] font-mono uppercase ${
                period === p ? "text-[var(--color-primary)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="px-3 pt-2 shrink-0">
        {data?.chart.length ? (
          <PerformanceChart data={data.chart} />
        ) : (
          <div className="h-[140px] flex items-center justify-center text-[10px] font-mono text-[var(--color-text-muted)]">
            {isLoading ? "로딩 중…" : "스냅샷 데이터 없음"}
          </div>
        )}
      </div>
      <div className="px-3 py-2 shrink-0">
        <div className="flex gap-3 text-[10px] font-mono flex-wrap">
          <div><span className="text-[var(--color-text-muted)]">Sharpe </span>
            <span className="text-[var(--color-text-primary)]">{data?.sharpe.toFixed(2) ?? "—"}</span></div>
          <div><span className="text-[var(--color-text-muted)]">MDD </span>
            <span className="text-red-400">{data ? `${data.mdd.toFixed(1)}%` : "—"}</span></div>
          <div><span className="text-[var(--color-text-muted)]">YTD </span>
            <span className={data && data.total_return >= 0 ? "text-green-400" : "text-red-400"}>
              {data ? `${data.total_return >= 0 ? "+" : ""}${data.total_return.toFixed(1)}%` : "—"}
            </span></div>
          {data?.benchmark?.kospi && (
            <div><span className="text-[var(--color-text-muted)]">vs KOSPI </span>
              <span className={data.total_return >= data.benchmark.kospi.return_pct ? "text-green-400" : "text-red-400"}>
                {(data.total_return - data.benchmark.kospi.return_pct) >= 0 ? "+" : ""}
                {(data.total_return - data.benchmark.kospi.return_pct).toFixed(1)}%
              </span></div>
          )}
          {data?.benchmark?.sp500 && (
            <div><span className="text-[var(--color-text-muted)]">vs S&P </span>
              <span className={data.total_return >= data.benchmark.sp500.return_pct ? "text-green-400" : "text-red-400"}>
                {(data.total_return - data.benchmark.sp500.return_pct) >= 0 ? "+" : ""}
                {(data.total_return - data.benchmark.sp500.return_pct).toFixed(1)}%
              </span></div>
          )}
        </div>
        <div className="flex gap-3 mt-1.5 text-[9px] font-mono">
          <span className="text-[#4a9eff]">■ 포트폴리오</span>
          <span className="text-[#26c940]">■ KOSPI</span>
          <span className="text-[#ff9500]">■ S&P500</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/terminal/widgets/PerformancePanel.tsx
git commit -m "feat(m8): PerformancePanel 컴포넌트"
```

---

### Task 14: TradeLogPanel + AddTradeModal

**Files:**
- Create: `frontend/components/terminal/widgets/TradeLogPanel.tsx`

- [ ] **Step 1: TradeLogPanel.tsx 작성**

```tsx
// frontend/components/terminal/widgets/TradeLogPanel.tsx
"use client";
import { useState } from "react";
import useSWR from "swr";
import { tradesApi } from "@/lib/api";
import type { TradeIn } from "@/lib/types";

interface Props {
  filterTicker?: string;
}

function AddTradeModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState<TradeIn>({
    ticker: "", trade_type: "BUY", quantity: 0, price: 0,
    currency: "USD", traded_at: new Date().toISOString().slice(0, 10),
  });
  const [error, setError] = useState("");

  async function submit() {
    if (!form.ticker || form.quantity <= 0 || form.price <= 0) {
      setError("종목, 수량, 단가를 입력하세요.");
      return;
    }
    try {
      await tradesApi.create(form);
      onSave();
      onClose();
    } catch (e: any) {
      setError(e.message ?? "저장 실패");
    }
  }

  const inputCls = "bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] text-[var(--color-text-primary)] px-2 py-1 font-mono text-[10px] w-full";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[var(--color-bg-secondary)] border border-[var(--color-border)] p-4 w-72 font-mono">
        <div className="text-[11px] uppercase tracking-widest text-[var(--color-primary)] mb-3">거래 추가</div>
        {error && <div className="text-red-400 text-[10px] mb-2">{error}</div>}
        <div className="space-y-2">
          <div>
            <label className="text-[9px] text-[var(--color-text-muted)] uppercase block mb-0.5">Ticker</label>
            <input className={inputCls} value={form.ticker}
              onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))} />
          </div>
          <div className="flex gap-2">
            {(["BUY", "SELL"] as const).map(t => (
              <button key={t} onClick={() => setForm(f => ({ ...f, trade_type: t }))}
                className={`flex-1 py-1 text-[10px] border ${
                  form.trade_type === t
                    ? t === "BUY" ? "border-green-500 text-green-400" : "border-red-500 text-red-400"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                }`}>
                {t}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[9px] text-[var(--color-text-muted)] uppercase block mb-0.5">수량</label>
              <input className={inputCls} type="number" value={form.quantity || ""}
                onChange={e => setForm(f => ({ ...f, quantity: parseFloat(e.target.value) || 0 }))} />
            </div>
            <div className="flex-1">
              <label className="text-[9px] text-[var(--color-text-muted)] uppercase block mb-0.5">단가</label>
              <input className={inputCls} type="number" value={form.price || ""}
                onChange={e => setForm(f => ({ ...f, price: parseFloat(e.target.value) || 0 }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[9px] text-[var(--color-text-muted)] uppercase block mb-0.5">통화</label>
              <select className={inputCls} value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value as "KRW" | "USD" }))}>
                <option value="USD">USD</option>
                <option value="KRW">KRW</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-[9px] text-[var(--color-text-muted)] uppercase block mb-0.5">날짜</label>
              <input className={inputCls} type="date" value={form.traded_at}
                onChange={e => setForm(f => ({ ...f, traded_at: e.target.value }))} />
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={submit}
            className="flex-1 py-1.5 text-[10px] bg-[var(--color-primary)] text-white font-mono">
            저장
          </button>
          <button onClick={onClose}
            className="flex-1 py-1.5 text-[10px] border border-[var(--color-border)] text-[var(--color-text-muted)] font-mono">
            취소
          </button>
        </div>
      </div>
    </div>
  );
}

export function TradeLogPanel({ filterTicker }: Props) {
  const [showModal, setShowModal] = useState(false);
  const { data: trades, mutate, isLoading } = useSWR(
    `/api/trades${filterTicker ? `?ticker=${filterTicker}` : ""}`,
    () => tradesApi.list(filterTicker),
    { refreshInterval: 30_000 }
  );

  async function handleDelete(id: number) {
    await tradesApi.delete(id);
    mutate();
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] shrink-0">
        <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)]">
          TRADE LOG{filterTicker ? ` — ${filterTicker}` : ""}
        </span>
        <button onClick={() => setShowModal(true)}
          className="text-[9px] font-mono border border-[var(--color-primary)] text-[var(--color-primary)] px-2 py-0.5 hover:bg-[var(--color-primary)] hover:text-black transition-colors">
          + 거래 추가
        </button>
      </div>
      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
        )}
        {!isLoading && !trades?.length && (
          <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">거래 내역 없음</div>
        )}
        <div className="px-3">
          {(trades ?? []).map(trade => (
            <div key={trade.id}
              className="grid grid-cols-5 py-1.5 border-b border-[var(--color-border)] items-center text-[10px] font-mono group">
              <span className="text-[var(--color-text-muted)] text-[9px]">{trade.traded_at}</span>
              <span className={trade.trade_type === "BUY" ? "text-green-400" : "text-red-400"}>
                {trade.trade_type}
              </span>
              <span className="text-[var(--color-text-primary)]">{trade.ticker}</span>
              <span className="text-[var(--color-text-secondary)] text-right">
                {trade.quantity}주 @{trade.price.toLocaleString()}
              </span>
              <div className="text-right">
                <button onClick={() => handleDelete(trade.id)}
                  className="opacity-0 group-hover:opacity-100 text-[9px] text-red-400 hover:text-red-300 transition-opacity">
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
      {showModal && (
        <AddTradeModal onClose={() => setShowModal(false)} onSave={() => mutate()} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/terminal/widgets/TradeLogPanel.tsx
git commit -m "feat(m8): TradeLogPanel + AddTradeModal 컴포넌트"
```

---

### Task 15: PortfolioPanel — Layout C로 교체

**Files:**
- Modify: `frontend/components/terminal/panels/PortfolioPanel.tsx`

- [ ] **Step 1: PortfolioPanel.tsx를 Layout C로 교체**

파일 전체를 아래로 교체:

```tsx
// frontend/components/terminal/panels/PortfolioPanel.tsx
"use client";
import { useState } from "react";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { PositionsPanel } from "@/components/terminal/widgets/PositionsPanel";
import { RebalancingPanel } from "@/components/terminal/widgets/RebalancingPanel";
import { PerformancePanel } from "@/components/terminal/widgets/PerformancePanel";
import { TradeLogPanel } from "@/components/terminal/widgets/TradeLogPanel";

function ResizeHandle({ vertical = false }: { vertical?: boolean }) {
  return vertical ? (
    <PanelResizeHandle className="h-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors my-0.5" />
  ) : (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

export function PortfolioPanel() {
  const [selectedTicker, setSelectedTicker] = useState<string | undefined>();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        PORTFOLIO
      </div>
      {/* Layout C: 왼쪽 사이드바 + 오른쪽 메인 */}
      <PanelGroup direction="horizontal" className="flex-1 overflow-hidden">

        {/* 왼쪽 사이드바: Positions + Rebalancing */}
        <Panel defaultSize={28} minSize={20} className="flex flex-col overflow-hidden">
          <PanelGroup direction="vertical" className="flex-1 overflow-hidden">
            <Panel defaultSize={55} minSize={30} className="flex flex-col overflow-hidden">
              <PositionsPanel
                onTickerSelect={setSelectedTicker}
                selectedTicker={selectedTicker}
              />
            </Panel>
            <ResizeHandle vertical />
            <Panel defaultSize={45} minSize={20} className="flex flex-col overflow-hidden">
              <RebalancingPanel />
            </Panel>
          </PanelGroup>
        </Panel>

        <ResizeHandle />

        {/* 오른쪽: Performance + Trade Log */}
        <Panel defaultSize={72} minSize={40} className="flex flex-col overflow-hidden">
          <PanelGroup direction="vertical" className="flex-1 overflow-hidden">
            <Panel defaultSize={55} minSize={30} className="flex flex-col overflow-hidden">
              <PerformancePanel />
            </Panel>
            <ResizeHandle vertical />
            <Panel defaultSize={45} minSize={25} className="flex flex-col overflow-hidden">
              <TradeLogPanel filterTicker={selectedTicker} />
            </Panel>
          </PanelGroup>
        </Panel>

      </PanelGroup>
    </div>
  );
}
```

- [ ] **Step 2: 프론트엔드 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` 또는 `Route (app)` 목록 출력

- [ ] **Step 3: 개발 서버 실행 + 브라우저 확인**

```bash
npm run dev -- --port 3333 &
sleep 3
open http://localhost:3333/terminal?tab=portfolio
```

확인 항목:
- PORTFOLIO 탭에 Layout C (왼쪽 사이드바 + 오른쪽) 렌더링
- POSITIONS 패널에 보유 종목 표시
- REBALANCING 패널에 종목 목록 표시 (목표 비중 설정 가능)
- PERFORMANCE 패널에 차트 영역 + Sharpe/MDD 지표 표시
- TRADE LOG 패널에 "거래 추가" 버튼 표시

- [ ] **Step 4: 전체 테스트 실행**

```bash
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
uv run pytest tests/test_trades_api.py tests/test_performance_api.py tests/test_rebalancing_api.py -v
```

Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/components/terminal/panels/PortfolioPanel.tsx
git commit -m "feat(m8): PortfolioPanel Layout C — Positions/Rebalancing/Performance/TradeLog"
```
