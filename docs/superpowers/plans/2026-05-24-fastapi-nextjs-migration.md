# FastAPI + Next.js 15 Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plotly Dash를 FastAPI REST API + Next.js 15 App Router로 전환하여 디자인 품질과 개발 유연성을 높인다.

**Architecture:** `core/` Python 레이어(repository, providers, strategies, scheduler)는 그대로 유지. `pages/` + `app.py`를 삭제하고 `api/` (FastAPI) + `frontend/` (Next.js 15 App Router)로 교체한다. Next.js는 `next.config.ts` rewrite를 통해 `/api/*` 요청을 FastAPI(localhost:8000)로 프록시하므로 CORS 설정이 불필요하다.

**Tech Stack:** Python 3.12, FastAPI 0.115, uvicorn, pytest + httpx, Next.js 15 App Router, TypeScript, Tailwind CSS v4, shadcn/ui, recharts 2, SWR 2

---

## 현재 상태 (이 플랜 시작 전)

- `core/` — 유지 (repository, ids, fx, prices/kis, strategies/sma_crossover, scheduler, auth)
- `pages/` — 삭제 예정
- `app.py` — 삭제 예정
- `requirements.txt` — dash 계열 제거 후 fastapi/uvicorn 추가
- `data/dudunomics.duckdb` — 유지 (스키마 호환)

---

## File Map

```
dudunomics/
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 앱 + CORS + 스케줄러 부트
│   ├── auth.py                  # HTTP Basic Auth 의존성
│   ├── models.py                # Pydantic 요청/응답 모델 전체
│   └── routers/
│       ├── __init__.py
│       ├── holdings.py          # GET/PUT/DELETE /api/holdings
│       ├── portfolio.py         # GET /api/portfolio/current, /history
│       ├── backtest.py          # POST /api/backtest/run, GET /api/backtest/runs
│       └── fx.py                # GET /api/fx/{pair}
├── core/                        # 기존 그대로
├── frontend/                    # Next.js 15
│   ├── app/
│   │   ├── layout.tsx           # 루트 레이아웃 + Nav
│   │   ├── page.tsx             # / → /portfolio redirect
│   │   ├── portfolio/
│   │   │   └── page.tsx
│   │   ├── holdings/
│   │   │   └── page.tsx
│   │   └── backtest/
│   │       └── page.tsx
│   ├── components/
│   │   ├── nav.tsx
│   │   ├── portfolio/
│   │   │   ├── kpi-cards.tsx
│   │   │   ├── weight-pie.tsx
│   │   │   ├── equity-curve.tsx
│   │   │   └── holdings-table.tsx
│   │   ├── holdings/
│   │   │   └── holdings-editor.tsx
│   │   └── backtest/
│   │       ├── backtest-form.tsx
│   │       └── backtest-result.tsx
│   ├── lib/
│   │   ├── types.ts             # TypeScript 타입 (Pydantic 모델과 1:1)
│   │   └── api.ts               # fetch 래퍼
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
├── tests/
│   ├── conftest.py              # DB 픽스처
│   ├── test_holdings_api.py
│   ├── test_portfolio_api.py
│   └── test_backtest_api.py
├── requirements.txt             # fastapi, uvicorn, httpx 추가 / dash 제거
├── Dockerfile                   # FastAPI만 빌드
├── render.yaml
└── .env.example
```

---

## Task 1: Cleanup + Python 의존성 업데이트

**Files:**
- Modify: `requirements.txt`
- Delete: `app.py`, `pages/` 디렉토리 전체
- Modify: `.env.example`

- [ ] **Step 1: Dash 관련 파일 삭제**

```bash
rm app.py
rm -rf pages/
```

- [ ] **Step 2: requirements.txt 교체**

`requirements.txt`를 아래 내용으로 전체 교체:

```
# API
fastapi==0.115.12
uvicorn[standard]==0.34.3
httpx==0.28.1
pydantic==2.11.4

# 데이터
yfinance==0.2.54
finance-datareader
pandas==2.2.3
numpy==2.1.3
python-kis==2.1.6

# DB
duckdb==1.2.2
duckdb-engine==0.14.1
sqlalchemy==2.0.41

# 스케줄러
apscheduler==3.10.4

# 백테스트
backtesting==0.3.3

# 유틸
python-dotenv==1.0.1
requests==2.32.3
pyyaml==6.0.2

# 테스트
pytest==8.3.5
pytest-anyio==0.0.0
```

- [ ] **Step 3: .env.example 업데이트**

```
# KIS Open API
KIS_APPKEY=your_appkey_here
KIS_SECRETKEY=your_secretkey_here
KIS_ACCOUNT_NO=12345678-01
KIS_ENV=real

# FMP (Phase β)
FMP_API_KEY=your_fmp_key_here

# Basic Auth (API 전체 보호)
BASIC_AUTH_USERNAME=admin
BASIC_AUTH_PASSWORD=changeme

# 앱
DB_PATH=data/dudunomics.duckdb
DEBUG=false
PORT=8000
```

- [ ] **Step 4: 의존성 재설치**

```bash
uv pip install -r requirements.txt
```

Expected: 오류 없이 설치 완료

- [ ] **Step 5: import 확인**

```bash
uv run python -c "import fastapi, uvicorn, httpx; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: commit**

```bash
git add requirements.txt .env.example
git rm -r app.py pages/
git commit -m "chore: remove Dash, add FastAPI deps"
```

---

## Task 2: Pydantic 모델 (api/models.py)

**Files:**
- Create: `api/__init__.py`
- Create: `api/models.py`

- [ ] **Step 1: api/__init__.py 생성**

```python
# api/__init__.py  (비어있음)
```

- [ ] **Step 2: api/models.py 작성**

```python
# api/models.py
from datetime import date, datetime
from pydantic import BaseModel, field_validator


class HoldingIn(BaseModel):
    name: str
    currency: str       # 'KRW' | 'USD'
    quantity: float
    avg_price: float

    @field_validator("currency")
    @classmethod
    def currency_valid(cls, v: str) -> str:
        if v not in ("KRW", "USD"):
            raise ValueError("currency must be KRW or USD")
        return v


class HoldingOut(HoldingIn):
    ticker: str
    updated_at: datetime


class CashUpdate(BaseModel):
    cash_krw: float = 0.0
    cash_usd: float = 0.0


class PortfolioRow(BaseModel):
    ticker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    currency: str
    market_value_krw: float
    return_pct: float
    weight_pct: float


class PortfolioSnapshot(BaseModel):
    rows: list[PortfolioRow]
    total_equity_krw: float
    total_with_cash_krw: float
    total_equity_usd: float
    total_with_cash_usd: float
    cash_krw: float
    cash_usd: float
    usdkrw: float
    updated_at: datetime


class SnapshotHistory(BaseModel):
    ts: datetime
    total_equity_krw: float
    total_with_cash_krw: float
    total_equity_usd: float
    total_with_cash_usd: float


class BacktestRunIn(BaseModel):
    ticker: str
    strategy: str
    params: dict
    period_start: date
    period_end: date


class BacktestRunOut(BaseModel):
    id: int
    ticker: str
    strategy: str
    params: dict
    period_start: date
    period_end: date
    total_return: float
    mdd: float
    sharpe: float
    equity_curve: list[dict]
    created_at: datetime


class FxRateOut(BaseModel):
    pair: str
    rate: float
    ts: datetime | None = None


class StrategiesOut(BaseModel):
    name: str
    params_schema: dict
```

- [ ] **Step 3: 모델 검증 테스트**

```bash
uv run python -c "
from api.models import HoldingIn, BacktestRunIn, CashUpdate
h = HoldingIn(name='삼성전자', currency='KRW', quantity=10, avg_price=70000)
print('HoldingIn OK:', h)
try:
    HoldingIn(name='x', currency='EUR', quantity=1, avg_price=1)
    assert False
except Exception as e:
    print('validation OK:', e)
"
```

Expected: `HoldingIn OK: ...` + `validation OK: ...`

- [ ] **Step 4: commit**

```bash
git add api/
git commit -m "feat: add Pydantic models for API layer"
```

---

## Task 3: Holdings API 라우터 + 테스트

**Files:**
- Create: `api/routers/__init__.py`
- Create: `api/routers/holdings.py`
- Create: `api/auth.py`
- Create: `tests/conftest.py`
- Create: `tests/test_holdings_api.py`

- [ ] **Step 1: api/auth.py 작성**

```python
# api/auth.py
import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    username = os.getenv("BASIC_AUTH_USERNAME")
    password = os.getenv("BASIC_AUTH_PASSWORD")
    if not username or not password:
        return  # 환경변수 미설정 시 인증 생략
    ok = (
        secrets.compare_digest(credentials.username.encode(), username.encode())
        and secrets.compare_digest(credentials.password.encode(), password.encode())
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
```

- [ ] **Step 2: api/routers/__init__.py 생성**

```python
# api/routers/__init__.py  (비어있음)
```

- [ ] **Step 3: api/routers/holdings.py 작성**

```python
# api/routers/holdings.py
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.models import CashUpdate, HoldingIn, HoldingOut
import core.repository as repo

router = APIRouter(prefix="/api/holdings", tags=["holdings"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[HoldingOut])
def list_holdings():
    return repo.get_holdings()


@router.get("/cash")
def get_cash():
    return {
        "cash_krw": float(repo.get_meta("cash_krw") or 0),
        "cash_usd": float(repo.get_meta("cash_usd") or 0),
    }


@router.put("/cash")
def update_cash(body: CashUpdate):
    repo.set_meta("cash_krw", str(body.cash_krw))
    repo.set_meta("cash_usd", str(body.cash_usd))
    return {"ok": True}


@router.put("/{ticker}", response_model=HoldingOut)
def upsert_holding(ticker: str, body: HoldingIn):
    repo.upsert_holding(
        ticker=ticker,
        name=body.name,
        currency=body.currency,
        quantity=body.quantity,
        avg_price=body.avg_price,
    )
    rows = repo.get_holdings()
    row = next((r for r in rows if r["ticker"] == ticker), None)
    if not row:
        raise HTTPException(status_code=404)
    return row


@router.delete("/{ticker}")
def delete_holding(ticker: str):
    repo.delete_holding(ticker)
    _backup_json()
    return {"ok": True}


def _backup_json():
    path = Path("data/holdings.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    holdings = repo.get_holdings()
    payload = {
        "holdings": [
            {"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
             "quantity": r["quantity"], "avg_price": r["avg_price"]}
            for r in holdings
        ],
        "cash_krw": float(repo.get_meta("cash_krw") or 0),
        "cash_usd": float(repo.get_meta("cash_usd") or 0),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: tests/conftest.py 작성**

```python
# tests/conftest.py
import pytest
import core.repository as repo_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """각 테스트마다 독립적인 임시 DuckDB 사용."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    repo_module._engine = None
    yield
    repo_module._engine = None


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)
```

- [ ] **Step 5: tests/test_holdings_api.py 작성**

```python
# tests/test_holdings_api.py


def test_list_holdings_empty(client):
    res = client.get("/api/holdings")
    assert res.status_code == 200
    assert res.json() == []


def test_upsert_and_list(client):
    res = client.put("/api/holdings/005930.KS", json={
        "name": "삼성전자", "currency": "KRW", "quantity": 10, "avg_price": 70000
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "005930.KS"
    assert data["quantity"] == 10

    res = client.get("/api/holdings")
    assert len(res.json()) == 1


def test_delete_holding(client):
    client.put("/api/holdings/AAPL", json={
        "name": "Apple", "currency": "USD", "quantity": 5, "avg_price": 175.0
    })
    res = client.delete("/api/holdings/AAPL")
    assert res.status_code == 200
    assert client.get("/api/holdings").json() == []


def test_cash_roundtrip(client):
    res = client.put("/api/holdings/cash", json={"cash_krw": 500000, "cash_usd": 200.0})
    assert res.status_code == 200
    res = client.get("/api/holdings/cash")
    data = res.json()
    assert data["cash_krw"] == 500000
    assert data["cash_usd"] == 200.0


def test_invalid_currency(client):
    res = client.put("/api/holdings/TSLA", json={
        "name": "Tesla", "currency": "EUR", "quantity": 1, "avg_price": 100
    })
    assert res.status_code == 422
```

- [ ] **Step 6: 최소 app 만들어서 테스트 실행 (main.py 임시 버전)**

```python
# api/main.py (임시 — Task 6에서 완성)
from fastapi import FastAPI
from api.routers.holdings import router as holdings_router

app = FastAPI()
app.include_router(holdings_router)
```

```bash
uv run pytest tests/test_holdings_api.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 7: commit**

```bash
git add api/ tests/
git commit -m "feat: holdings API router + tests"
```

---

## Task 4: Portfolio API 라우터 + 테스트

**Files:**
- Create: `api/routers/portfolio.py`
- Create: `tests/test_portfolio_api.py`

- [ ] **Step 1: api/routers/portfolio.py 작성**

```python
# api/routers/portfolio.py
from datetime import datetime
from fastapi import APIRouter, Depends
from api.auth import require_auth
from api.models import PortfolioRow, PortfolioSnapshot, SnapshotHistory
import core.repository as repo
from core.fx import get_fx_provider
from core.ids import detect_currency
from core.prices.kis import KISPriceProvider

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(require_auth)])

_price_provider = KISPriceProvider()
_fx_provider = get_fx_provider()


@router.get("/current", response_model=PortfolioSnapshot)
def get_current():
    holdings = repo.get_holdings()
    if not holdings:
        return PortfolioSnapshot(
            rows=[], total_equity_krw=0, total_with_cash_krw=0,
            total_equity_usd=0, total_with_cash_usd=0,
            cash_krw=0, cash_usd=0, usdkrw=1350.0, updated_at=datetime.now()
        )

    tickers = [h["ticker"] for h in holdings]
    prices = _price_provider.get_current_prices(tickers)
    usdkrw = _get_usdkrw()

    cash_krw = float(repo.get_meta("cash_krw") or 0)
    cash_usd = float(repo.get_meta("cash_usd") or 0)
    cash_total_krw = cash_krw + cash_usd * usdkrw
    cash_total_usd = cash_krw / usdkrw + cash_usd

    rows: list[PortfolioRow] = []
    total_equity_krw = 0.0
    total_equity_usd = 0.0

    for h in holdings:
        ticker = h["ticker"]
        if ticker not in prices:
            continue
        p = prices[ticker]
        mv = p.current * h["quantity"]
        mv_krw = mv if p.currency == "KRW" else mv * usdkrw
        mv_usd = mv / usdkrw if p.currency == "KRW" else mv
        total_equity_krw += mv_krw
        total_equity_usd += mv_usd
        ret_pct = (p.current - h["avg_price"]) / h["avg_price"] * 100 if h["avg_price"] else 0
        rows.append(PortfolioRow(
            ticker=ticker, name=h["name"], quantity=h["quantity"],
            avg_price=h["avg_price"], current_price=p.current,
            currency=p.currency, market_value_krw=mv_krw,
            return_pct=round(ret_pct, 2), weight_pct=0,
        ))

    denom = total_equity_krw or 1
    for r in rows:
        r.weight_pct = round(r.market_value_krw / denom * 100, 2)

    return PortfolioSnapshot(
        rows=rows,
        total_equity_krw=total_equity_krw,
        total_with_cash_krw=total_equity_krw + cash_total_krw,
        total_equity_usd=total_equity_usd,
        total_with_cash_usd=total_equity_usd + cash_total_usd,
        cash_krw=cash_total_krw,
        cash_usd=cash_total_usd,
        usdkrw=usdkrw,
        updated_at=datetime.now(),
    )


@router.get("/history", response_model=list[SnapshotHistory])
def get_history(limit: int = 400):
    rows = repo.get_snapshots(limit=limit)
    return [
        SnapshotHistory(
            ts=r["ts"],
            total_equity_krw=r["total_equity_krw"],
            total_with_cash_krw=r["total_with_cash_krw"],
            total_equity_usd=r["total_equity_usd"],
            total_with_cash_usd=r["total_with_cash_usd"],
        )
        for r in rows
    ]


def _get_usdkrw() -> float:
    cached = repo.get_latest_fx_rate("USDKRW")
    if cached:
        return cached
    try:
        return _fx_provider.get_rate("USDKRW")
    except Exception:
        return 1350.0
```

- [ ] **Step 2: tests/test_portfolio_api.py 작성**

```python
# tests/test_portfolio_api.py
from unittest.mock import patch, MagicMock
from core.prices.base import Price
import core.repository as repo


def test_portfolio_empty(client):
    res = client.get("/api/portfolio/current")
    assert res.status_code == 200
    data = res.json()
    assert data["rows"] == []
    assert data["total_equity_krw"] == 0


def test_portfolio_with_holdings(client):
    repo.upsert_holding("005930.KS", "삼성전자", "KRW", 10, 70000)
    repo.upsert_holding("AAPL", "Apple", "USD", 5, 175.0)

    mock_prices = {
        "005930.KS": Price(ticker="005930.KS", current=75000, currency="KRW"),
        "AAPL": Price(ticker="AAPL", current=180.0, currency="USD"),
    }
    with patch("api.routers.portfolio._price_provider.get_current_prices", return_value=mock_prices), \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        res = client.get("/api/portfolio/current")

    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 2
    assert data["total_equity_krw"] > 0

    # 005930.KS: 75000 * 10 = 750000 KRW
    krw_row = next(r for r in data["rows"] if r["ticker"] == "005930.KS")
    assert krw_row["market_value_krw"] == 750000
    assert krw_row["return_pct"] == pytest.approx((75000 - 70000) / 70000 * 100, rel=1e-3)


def test_portfolio_history_empty(client):
    res = client.get("/api/portfolio/history")
    assert res.status_code == 200
    assert res.json() == []


import pytest
```

- [ ] **Step 3: main.py에 portfolio 라우터 추가**

`api/main.py`를 수정:

```python
from fastapi import FastAPI
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router

app = FastAPI()
app.include_router(holdings_router)
app.include_router(portfolio_router)
```

- [ ] **Step 4: 테스트 실행**

```bash
uv run pytest tests/test_holdings_api.py tests/test_portfolio_api.py -v
```

Expected: 모든 테스트 PASSED

- [ ] **Step 5: commit**

```bash
git add api/routers/portfolio.py tests/test_portfolio_api.py api/main.py
git commit -m "feat: portfolio API router + tests"
```

---

## Task 5: FX + Backtest API 라우터 + 테스트

**Files:**
- Create: `api/routers/fx.py`
- Create: `api/routers/backtest.py`
- Create: `tests/test_backtest_api.py`

- [ ] **Step 1: api/routers/fx.py 작성**

```python
# api/routers/fx.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.models import FxRateOut
import core.repository as repo
from core.fx import get_fx_provider

router = APIRouter(prefix="/api/fx", tags=["fx"], dependencies=[Depends(require_auth)])
_fx_provider = get_fx_provider()


@router.get("/{pair}", response_model=FxRateOut)
def get_fx_rate(pair: str):
    pair = pair.upper()
    cached = repo.get_latest_fx_rate(pair)
    if cached:
        return FxRateOut(pair=pair, rate=cached)
    try:
        rate = _fx_provider.get_rate(pair)
        return FxRateOut(pair=pair, rate=rate)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"환율 조회 실패: {e}")
```

- [ ] **Step 2: api/routers/backtest.py 작성**

```python
# api/routers/backtest.py
from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
import yfinance as yf
from backtesting import Backtest

from api.auth import require_auth
from api.models import BacktestRunIn, BacktestRunOut, StrategiesOut
import core.repository as repo
from core.strategies.base import get_strategy, list_strategies
import core.strategies.sma_crossover  # 전략 등록

router = APIRouter(prefix="/api/backtest", tags=["backtest"], dependencies=[Depends(require_auth)])


@router.get("/strategies", response_model=list[StrategiesOut])
def get_strategies():
    return list_strategies()


@router.post("/run", response_model=BacktestRunOut)
def run_backtest(body: BacktestRunIn):
    try:
        df = yf.download(
            body.ticker,
            start=str(body.period_start),
            end=str(body.period_end),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            raise HTTPException(status_code=422, detail=f"{body.ticker} 데이터 없음")

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        strat = get_strategy(body.strategy)
        bt_class = strat.to_backtesting_class(body.params)
        bt_obj = Backtest(df, bt_class, cash=10_000_000, commission=0.002)
        stats = bt_obj.run()

        equity = stats._equity_curve["Equity"]
        curve_data = [{"ts": str(t.date()), "equity": float(v)} for t, v in equity.items()]

        run_id = repo.insert_backtest_run(
            strategy=body.strategy,
            params=body.params,
            ticker=body.ticker,
            period_start=body.period_start,
            period_end=body.period_end,
            total_return=float(stats["Return [%]"]),
            mdd=float(stats["Max. Drawdown [%]"]),
            sharpe=float(stats.get("Sharpe Ratio") or 0),
            equity_curve=curve_data,
        )

        from datetime import datetime
        return BacktestRunOut(
            id=run_id,
            ticker=body.ticker,
            strategy=body.strategy,
            params=body.params,
            period_start=body.period_start,
            period_end=body.period_end,
            total_return=float(stats["Return [%]"]),
            mdd=float(stats["Max. Drawdown [%]"]),
            sharpe=float(stats.get("Sharpe Ratio") or 0),
            equity_curve=curve_data,
            created_at=datetime.now(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: tests/test_backtest_api.py 작성**

```python
# tests/test_backtest_api.py
import numpy as np
import pandas as pd
from unittest.mock import patch


def _make_fake_ohlcv(n=300):
    """재현 가능한 합성 OHLCV 데이터."""
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(1_000_000, 5_000_000, n),
    }, index=idx)
    return df


def test_list_strategies(client):
    res = client.get("/api/backtest/strategies")
    assert res.status_code == 200
    names = [s["name"] for s in res.json()]
    assert "SMA Crossover" in names


def test_run_backtest_synthetic(client):
    fake_df = _make_fake_ohlcv()
    with patch("yfinance.download", return_value=fake_df):
        res = client.post("/api/backtest/run", json={
            "ticker": "TEST",
            "strategy": "SMA Crossover",
            "params": {"fast": 5, "slow": 20},
            "period_start": "2021-01-01",
            "period_end": "2022-01-01",
        })
    assert res.status_code == 200
    data = res.json()
    assert "total_return" in data
    assert "equity_curve" in data
    assert len(data["equity_curve"]) > 0
    assert data["id"] >= 1


def test_run_backtest_empty_data(client):
    with patch("yfinance.download", return_value=pd.DataFrame()):
        res = client.post("/api/backtest/run", json={
            "ticker": "FAKE",
            "strategy": "SMA Crossover",
            "params": {"fast": 5, "slow": 20},
            "period_start": "2021-01-01",
            "period_end": "2022-01-01",
        })
    assert res.status_code == 422
```

- [ ] **Step 4: main.py에 라우터 추가**

`api/main.py`를 수정:

```python
from fastapi import FastAPI
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router
from api.routers.fx import router as fx_router
from api.routers.backtest import router as backtest_router

app = FastAPI()
app.include_router(holdings_router)
app.include_router(portfolio_router)
app.include_router(fx_router)
app.include_router(backtest_router)
```

- [ ] **Step 5: 전체 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 PASSED

- [ ] **Step 6: commit**

```bash
git add api/routers/fx.py api/routers/backtest.py tests/test_backtest_api.py api/main.py
git commit -m "feat: fx + backtest API routers + tests"
```

---

## Task 6: FastAPI main.py 완성 (CORS + Auth + 스케줄러)

**Files:**
- Modify: `api/main.py`
- Modify: `Dockerfile`

- [ ] **Step 1: api/main.py 최종 버전으로 교체**

```python
# api/main.py
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.repository import get_engine
from core.scheduler import create_scheduler
from api.routers.holdings import router as holdings_router
from api.routers.portfolio import router as portfolio_router
from api.routers.fx import router as fx_router
from api.routers.backtest import router as backtest_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    get_engine()  # DB 스키마 초기화
    _scheduler = create_scheduler()
    _scheduler.start()
    yield
    if _scheduler:
        _scheduler.shutdown()


app = FastAPI(title="Dudunomics API", lifespan=lifespan)

# CORS — Next.js dev 서버(3000) + 프로덕션 도메인
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(holdings_router)
app.include_router(portfolio_router)
app.include_router(fx_router)
app.include_router(backtest_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 서버 기동 확인**

```bash
uv run uvicorn api.main:app --reload --port 8000 &
sleep 3
curl http://localhost:8000/health
pkill -f "uvicorn api.main"
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Dockerfile 업데이트 (FastAPI 전용)**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: render.yaml 업데이트**

```yaml
services:
  - type: web
    name: dudunomics-api
    env: docker
    dockerfilePath: ./Dockerfile
    disk:
      name: data
      mountPath: /app/data
      sizeGB: 1
    envVars:
      - key: KIS_APPKEY
        sync: false
      - key: KIS_SECRETKEY
        sync: false
      - key: KIS_ACCOUNT_NO
        sync: false
      - key: KIS_ENV
        value: real
      - key: FMP_API_KEY
        sync: false
      - key: BASIC_AUTH_USERNAME
        sync: false
      - key: BASIC_AUTH_PASSWORD
        sync: false
      - key: ALLOWED_ORIGINS
        sync: false   # Vercel 도메인 입력
```

- [ ] **Step 5: 전체 테스트 재실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 PASSED

- [ ] **Step 6: commit**

```bash
git add api/main.py Dockerfile render.yaml
git commit -m "feat: FastAPI main with lifespan scheduler + CORS"
```

---

## Task 7: Next.js 15 프로젝트 초기화

**Files:**
- Create: `frontend/` 디렉토리 전체

- [ ] **Step 1: Next.js 프로젝트 생성**

```bash
cd /Users/user/Development/private/dudunomics
npx create-next-app@15 frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir \
  --import-alias "@/*" \
  --yes
```

- [ ] **Step 2: 추가 의존성 설치**

```bash
cd frontend
npm install recharts swr
npm install -D @types/recharts
npx shadcn@latest init --defaults --yes
npx shadcn@latest add card table button input badge tabs select label
```

- [ ] **Step 3: next.config.ts 설정 (API 프록시)**

`frontend/next.config.ts`를 아래 내용으로 교체:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 4: .env.local 생성**

```bash
cat > frontend/.env.local << 'EOF'
API_URL=http://localhost:8000
EOF
```

- [ ] **Step 5: 개발 서버 기동 확인**

FastAPI 서버가 실행 중인 상태에서:

```bash
cd frontend && npm run dev &
sleep 5
curl http://localhost:3000/api/health
pkill -f "next dev"
```

Expected: `{"status":"ok"}` (프록시 경유)

- [ ] **Step 6: commit**

```bash
cd ..
git add frontend/
git commit -m "chore: init Next.js 15 + shadcn/ui + recharts"
```

---

## Task 8: API 클라이언트 + TypeScript 타입

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`

- [ ] **Step 1: frontend/lib/types.ts 작성**

```typescript
// frontend/lib/types.ts

export interface HoldingIn {
  name: string;
  currency: "KRW" | "USD";
  quantity: number;
  avg_price: number;
}

export interface HoldingOut extends HoldingIn {
  ticker: string;
  updated_at: string;
}

export interface CashUpdate {
  cash_krw: number;
  cash_usd: number;
}

export interface PortfolioRow {
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  currency: string;
  market_value_krw: number;
  return_pct: number;
  weight_pct: number;
}

export interface PortfolioSnapshot {
  rows: PortfolioRow[];
  total_equity_krw: number;
  total_with_cash_krw: number;
  total_equity_usd: number;
  total_with_cash_usd: number;
  cash_krw: number;
  cash_usd: number;
  usdkrw: number;
  updated_at: string;
}

export interface SnapshotHistory {
  ts: string;
  total_equity_krw: number;
  total_with_cash_krw: number;
  total_equity_usd: number;
  total_with_cash_usd: number;
}

export interface StrategyDef {
  name: string;
  params_schema: Record<string, {
    type: string;
    default: number;
    label: string;
    min: number;
    max: number;
  }>;
}

export interface BacktestRunIn {
  ticker: string;
  strategy: string;
  params: Record<string, number>;
  period_start: string;
  period_end: string;
}

export interface BacktestRunOut {
  id: number;
  ticker: string;
  strategy: string;
  params: Record<string, number>;
  period_start: string;
  period_end: string;
  total_return: number;
  mdd: number;
  sharpe: number;
  equity_curve: Array<{ ts: string; equity: number }>;
  created_at: string;
}
```

- [ ] **Step 2: frontend/lib/api.ts 작성**

```typescript
// frontend/lib/api.ts
import type {
  BacktestRunIn, BacktestRunOut, CashUpdate,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Holdings ──────────────────────────────────────────────────────────────────
export const holdingsApi = {
  list: () => request<HoldingOut[]>("/api/holdings"),
  upsert: (ticker: string, body: HoldingIn) =>
    request<HoldingOut>(`/api/holdings/${ticker}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (ticker: string) =>
    request<{ ok: boolean }>(`/api/holdings/${ticker}`, { method: "DELETE" }),
  getCash: () => request<{ cash_krw: number; cash_usd: number }>("/api/holdings/cash"),
  updateCash: (body: CashUpdate) =>
    request<{ ok: boolean }>("/api/holdings/cash", { method: "PUT", body: JSON.stringify(body) }),
};

// ── Portfolio ─────────────────────────────────────────────────────────────────
export const portfolioApi = {
  current: () => request<PortfolioSnapshot>("/api/portfolio/current"),
  history: (limit = 400) => request<SnapshotHistory[]>(`/api/portfolio/history?limit=${limit}`),
};

// ── Backtest ──────────────────────────────────────────────────────────────────
export const backtestApi = {
  strategies: () => request<StrategyDef[]>("/api/backtest/strategies"),
  run: (body: BacktestRunIn) =>
    request<BacktestRunOut>("/api/backtest/run", { method: "POST", body: JSON.stringify(body) }),
};
```

- [ ] **Step 3: TypeScript 컴파일 확인**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 4: commit**

```bash
git add frontend/lib/
git commit -m "feat: API client + TypeScript types"
```

---

## Task 9: 공유 레이아웃 + 네비게이션

**Files:**
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/components/nav.tsx`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: frontend/components/nav.tsx 작성**

```tsx
// frontend/components/nav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/holdings", label: "보유종목" },
  { href: "/backtest", label: "백테스트" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <div className="mx-auto flex h-14 max-w-screen-xl items-center gap-6 px-6">
        <Link href="/portfolio" className="text-lg font-bold tracking-tight">
          📈 Dudunomics
        </Link>
        <div className="flex gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname.startsWith(href)
                  ? "bg-slate-100 text-slate-900"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: frontend/app/layout.tsx 수정**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Dudunomics",
  description: "글로벌 포트폴리오 + 퀀트 분석",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className={`${inter.className} min-h-screen bg-slate-50 antialiased`}>
        <Nav />
        <main className="mx-auto max-w-screen-xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: frontend/app/page.tsx (루트 → /portfolio 리다이렉트)**

```tsx
// frontend/app/page.tsx
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/portfolio");
}
```

- [ ] **Step 4: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ Compiled successfully` 또는 오류 없음

- [ ] **Step 5: commit**

```bash
git add frontend/app/layout.tsx frontend/app/page.tsx frontend/components/nav.tsx
git commit -m "feat: shared layout + navigation"
```

---

## Task 10: Portfolio 페이지

**Files:**
- Create: `frontend/app/portfolio/page.tsx`
- Create: `frontend/components/portfolio/kpi-cards.tsx`
- Create: `frontend/components/portfolio/weight-pie.tsx`
- Create: `frontend/components/portfolio/equity-curve.tsx`
- Create: `frontend/components/portfolio/holdings-table.tsx`

- [ ] **Step 1: frontend/components/portfolio/kpi-cards.tsx 작성**

```tsx
// frontend/components/portfolio/kpi-cards.tsx
import { Card, CardContent } from "@/components/ui/card";
import type { PortfolioSnapshot } from "@/lib/types";

interface Props {
  snapshot: PortfolioSnapshot;
  currency: "KRW" | "USD";
  weightMode: "equity" | "total";
}

function fmt(val: number, currency: string) {
  const sym = currency === "KRW" ? "₩" : "$";
  return `${sym}${val.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
}

export function KpiCards({ snapshot, currency, weightMode }: Props) {
  const usdkrw = snapshot.usdkrw;
  const toDisplay = (krw: number) =>
    currency === "KRW" ? krw : krw / usdkrw;

  const equity = toDisplay(snapshot.total_equity_krw);
  const withCash = toDisplay(snapshot.total_with_cash_krw);
  const cash = toDisplay(snapshot.cash_krw);

  // 수익률: 현재 평가액 vs 비용 (history 없이 단순 추정 — snapshot에는 cost 없음)
  const items = [
    { label: "주식 평가액", value: fmt(equity, currency) },
    { label: "현금 포함", value: fmt(withCash, currency) },
    { label: "현금", value: fmt(cash, currency) },
    { label: "USD/KRW", value: `₩${usdkrw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: frontend/components/portfolio/weight-pie.tsx 작성**

```tsx
// frontend/components/portfolio/weight-pie.tsx
"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { PortfolioRow } from "@/lib/types";

const COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"];

interface Props { rows: PortfolioRow[] }

export function WeightPie({ rows }: Props) {
  const data = rows.map((r) => ({ name: r.ticker, value: r.weight_pct }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
             outerRadius={90} innerRadius={50} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: frontend/components/portfolio/equity-curve.tsx 작성**

```tsx
// frontend/components/portfolio/equity-curve.tsx
"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import type { SnapshotHistory } from "@/lib/types";

interface Props {
  history: SnapshotHistory[];
  currency: "KRW" | "USD";
}

export function EquityCurve({ history, currency }: Props) {
  const key = currency === "KRW" ? "total_equity_krw" : "total_equity_usd";
  const sym = currency === "KRW" ? "₩" : "$";
  const data = [...history].reverse().map((h) => ({
    ts: h.ts.slice(0, 16).replace("T", " "),
    value: h[key],
  }));

  if (data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">스냅샷 없음 — 5분 후 자동 생성됩니다.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="ts" tick={{ fontSize: 11 }} tickCount={6} />
        <YAxis tickFormatter={(v) => `${sym}${(v / 1_000_000).toFixed(1)}M`} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => `${sym}${v.toLocaleString()}`} />
        <Area type="monotone" dataKey="value" stroke="#3b82f6" fill="url(#eq)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 4: frontend/components/portfolio/holdings-table.tsx 작성**

```tsx
// frontend/components/portfolio/holdings-table.tsx
import { Badge } from "@/components/ui/badge";
import type { PortfolioRow } from "@/lib/types";

interface Props { rows: PortfolioRow[]; currency: "KRW" | "USD"; usdkrw: number }

export function HoldingsTable({ rows, currency, usdkrw }: Props) {
  const sym = currency === "KRW" ? "₩" : "$";
  const convert = (krw: number) => currency === "KRW" ? krw : krw / usdkrw;

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="w-full text-sm">
        <thead className="border-b bg-slate-50 text-xs uppercase text-muted-foreground">
          <tr>
            {["티커","종목명","수량","평균단가","현재가","평가금액","수익률","비중"].map((h) => (
              <th key={h} className="px-4 py-3 text-right first:text-left">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker} className="border-b last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 font-mono font-medium">{r.ticker}</td>
              <td className="px-4 py-3 text-right text-muted-foreground">{r.name}</td>
              <td className="px-4 py-3 text-right">{r.quantity.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{r.avg_price.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{r.current_price.toLocaleString()}</td>
              <td className="px-4 py-3 text-right font-medium">
                {sym}{convert(r.market_value_krw).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
              </td>
              <td className="px-4 py-3 text-right">
                <Badge variant={r.return_pct >= 0 ? "default" : "destructive"}
                  className={r.return_pct >= 0 ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-100" : ""}>
                  {r.return_pct >= 0 ? "+" : ""}{r.return_pct.toFixed(2)}%
                </Badge>
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">{r.weight_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: frontend/app/portfolio/page.tsx 작성**

```tsx
// frontend/app/portfolio/page.tsx
"use client";

import useSWR from "swr";
import { useState } from "react";
import { portfolioApi } from "@/lib/api";
import { KpiCards } from "@/components/portfolio/kpi-cards";
import { WeightPie } from "@/components/portfolio/weight-pie";
import { EquityCurve } from "@/components/portfolio/equity-curve";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PortfolioPage() {
  const [currency, setCurrency] = useState<"KRW" | "USD">("KRW");
  const [weightMode, setWeightMode] = useState<"equity" | "total">("equity");

  const { data: snapshot, error: snapErr, isLoading: snapLoading } =
    useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  const { data: history } =
    useSWR("/api/portfolio/history", portfolioApi.history, { refreshInterval: 60_000 });

  if (snapLoading) return <div className="py-12 text-center text-muted-foreground">로딩 중…</div>;
  if (snapErr) return <div className="py-12 text-center text-destructive">데이터 로드 실패. API 서버를 확인하세요.</div>;
  if (!snapshot) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">포트폴리오</h1>
        <div className="flex gap-3">
          <Tabs value={currency} onValueChange={(v) => setCurrency(v as "KRW" | "USD")}>
            <TabsList>
              <TabsTrigger value="KRW">KRW</TabsTrigger>
              <TabsTrigger value="USD">USD</TabsTrigger>
            </TabsList>
          </Tabs>
          <Tabs value={weightMode} onValueChange={(v) => setWeightMode(v as "equity" | "total")}>
            <TabsList>
              <TabsTrigger value="equity">주식만</TabsTrigger>
              <TabsTrigger value="total">주식+현금</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      <KpiCards snapshot={snapshot} currency={currency} weightMode={weightMode} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-base">비중</CardTitle></CardHeader>
          <CardContent className="pb-4">
            <WeightPie rows={snapshot.rows} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="text-base">평가액 추이</CardTitle></CardHeader>
          <CardContent className="pb-4">
            <EquityCurve history={history ?? []} currency={currency} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">보유종목</CardTitle></CardHeader>
        <CardContent className="p-0">
          <HoldingsTable rows={snapshot.rows} currency={currency} usdkrw={snapshot.usdkrw} />
        </CardContent>
      </Card>

      <p className="text-right text-xs text-muted-foreground">
        마지막 갱신: {new Date(snapshot.updated_at).toLocaleString("ko-KR")}
      </p>
    </div>
  );
}
```

- [ ] **Step 6: 빌드 확인**

```bash
cd frontend && npx tsc --noEmit && npm run build 2>&1 | tail -10
```

Expected: 타입 오류 없음

- [ ] **Step 7: commit**

```bash
git add frontend/app/portfolio/ frontend/components/portfolio/
git commit -m "feat: portfolio page with KPI cards, pie chart, equity curve, table"
```

---

## Task 11: Holdings Editor 페이지

**Files:**
- Create: `frontend/app/holdings/page.tsx`
- Create: `frontend/components/holdings/holdings-editor.tsx`

- [ ] **Step 1: frontend/components/holdings/holdings-editor.tsx 작성**

```tsx
// frontend/components/holdings/holdings-editor.tsx
"use client";

import { useState } from "react";
import { holdingsApi } from "@/lib/api";
import type { HoldingOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

interface Row {
  id: string;  // 클라이언트 키
  ticker: string;
  name: string;
  currency: "KRW" | "USD";
  quantity: string;
  avg_price: string;
  saved: boolean;
}

function toRow(h: HoldingOut): Row {
  return {
    id: h.ticker,
    ticker: h.ticker,
    name: h.name,
    currency: h.currency as "KRW" | "USD",
    quantity: String(h.quantity),
    avg_price: String(h.avg_price),
    saved: true,
  };
}

interface Props {
  initialHoldings: HoldingOut[];
  initialCashKrw: number;
  initialCashUsd: number;
}

export function HoldingsEditor({ initialHoldings, initialCashKrw, initialCashUsd }: Props) {
  const [rows, setRows] = useState<Row[]>(initialHoldings.map(toRow));
  const [cashKrw, setCashKrw] = useState(String(initialCashKrw));
  const [cashUsd, setCashUsd] = useState(String(initialCashUsd));
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      { id: crypto.randomUUID(), ticker: "", name: "", currency: "KRW", quantity: "0", avg_price: "0", saved: false },
    ]);

  const update = (id: string, field: keyof Row, value: string) =>
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value, saved: false } : r)));

  const remove = async (row: Row) => {
    if (row.ticker && row.saved) await holdingsApi.delete(row.ticker);
    setRows((prev) => prev.filter((r) => r.id !== row.id));
  };

  const save = async () => {
    setSaving(true);
    setStatus("");
    try {
      const existing = initialHoldings.map((h) => h.ticker);
      const current = rows.map((r) => r.ticker).filter(Boolean);
      for (const t of existing) {
        if (!current.includes(t)) await holdingsApi.delete(t);
      }
      for (const row of rows) {
        if (!row.ticker) continue;
        await holdingsApi.upsert(row.ticker, {
          name: row.name || row.ticker,
          currency: row.currency,
          quantity: parseFloat(row.quantity) || 0,
          avg_price: parseFloat(row.avg_price) || 0,
        });
      }
      await holdingsApi.updateCash({
        cash_krw: parseFloat(cashKrw) || 0,
        cash_usd: parseFloat(cashUsd) || 0,
      });
      setRows((prev) => prev.map((r) => ({ ...r, saved: true })));
      setStatus("저장 완료 ✓");
    } catch (e: unknown) {
      setStatus(`오류: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 현금 입력 */}
      <div className="rounded-lg border bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-muted-foreground">현금 잔고</h3>
        <div className="flex flex-wrap gap-4">
          <div className="space-y-1">
            <Label>현금 (KRW)</Label>
            <Input value={cashKrw} onChange={(e) => setCashKrw(e.target.value)}
              type="number" className="w-40" />
          </div>
          <div className="space-y-1">
            <Label>현금 (USD)</Label>
            <Input value={cashUsd} onChange={(e) => setCashUsd(e.target.value)}
              type="number" className="w-40" />
          </div>
        </div>
      </div>

      {/* 종목 테이블 */}
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b bg-slate-50 text-xs uppercase text-muted-foreground">
            <tr>
              {["티커", "종목명", "통화", "수량", "평균단가", "상태", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b last:border-0">
                <td className="px-4 py-2">
                  <Input value={row.ticker} onChange={(e) => update(row.id, "ticker", e.target.value)}
                    className="h-8 w-32 font-mono" placeholder="005930.KS" />
                </td>
                <td className="px-4 py-2">
                  <Input value={row.name} onChange={(e) => update(row.id, "name", e.target.value)}
                    className="h-8 w-36" placeholder="종목명" />
                </td>
                <td className="px-4 py-2">
                  <Select value={row.currency} onValueChange={(v) => update(row.id, "currency", v)}>
                    <SelectTrigger className="h-8 w-20"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="KRW">KRW</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                    </SelectContent>
                  </Select>
                </td>
                <td className="px-4 py-2">
                  <Input value={row.quantity} onChange={(e) => update(row.id, "quantity", e.target.value)}
                    type="number" className="h-8 w-24" />
                </td>
                <td className="px-4 py-2">
                  <Input value={row.avg_price} onChange={(e) => update(row.id, "avg_price", e.target.value)}
                    type="number" className="h-8 w-28" />
                </td>
                <td className="px-4 py-2">
                  <Badge variant={row.saved ? "outline" : "secondary"}>
                    {row.saved ? "저장됨" : "미저장"}
                  </Badge>
                </td>
                <td className="px-4 py-2">
                  <Button variant="ghost" size="sm" onClick={() => remove(row)}
                    className="h-8 text-destructive hover:text-destructive">삭제</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={addRow}>+ 행 추가</Button>
        <Button onClick={save} disabled={saving}>
          {saving ? "저장 중…" : "저장"}
        </Button>
        {status && <span className={`text-sm ${status.startsWith("오류") ? "text-destructive" : "text-emerald-600"}`}>{status}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: frontend/app/holdings/page.tsx 작성**

```tsx
// frontend/app/holdings/page.tsx
import { holdingsApi } from "@/lib/api";
import { HoldingsEditor } from "@/components/holdings/holdings-editor";

export default async function HoldingsPage() {
  // 서버 컴포넌트에서 초기 데이터 fetch
  const [holdings, cash] = await Promise.all([
    holdingsApi.list().catch(() => []),
    holdingsApi.getCash().catch(() => ({ cash_krw: 0, cash_usd: 0 })),
  ]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">보유종목 편집</h1>
      <HoldingsEditor
        initialHoldings={holdings}
        initialCashKrw={cash.cash_krw}
        initialCashUsd={cash.cash_usd}
      />
    </div>
  );
}
```

- [ ] **Step 3: 빌드 확인**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 4: commit**

```bash
git add frontend/app/holdings/ frontend/components/holdings/
git commit -m "feat: holdings editor page"
```

---

## Task 12: Backtest 페이지

**Files:**
- Create: `frontend/app/backtest/page.tsx`
- Create: `frontend/components/backtest/backtest-form.tsx`
- Create: `frontend/components/backtest/backtest-result.tsx`

- [ ] **Step 1: frontend/components/backtest/backtest-result.tsx 작성**

```tsx
// frontend/components/backtest/backtest-result.tsx
"use client";

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BacktestRunOut } from "@/lib/types";

export function BacktestResult({ result }: { result: BacktestRunOut }) {
  const kpis = [
    { label: "총 수익률", value: `${result.total_return >= 0 ? "+" : ""}${result.total_return.toFixed(2)}%`, pos: result.total_return >= 0 },
    { label: "MDD", value: `${result.mdd.toFixed(2)}%`, pos: false },
    { label: "Sharpe", value: result.sharpe.toFixed(2), pos: result.sharpe >= 1 },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {kpis.map(({ label, value, pos }) => (
          <Card key={label}>
            <CardContent className="pt-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className={`mt-1 text-2xl font-bold ${pos ? "text-emerald-600" : "text-rose-600"}`}>{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="pt-4">
          <p className="mb-2 text-sm font-medium">자산 곡선</p>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={result.equity_curve} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
              <defs>
                <linearGradient id="bt" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="ts" tick={{ fontSize: 10 }} tickCount={8} />
              <YAxis tickFormatter={(v) => `₩${(v / 1_000_000).toFixed(1)}M`} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => `₩${v.toLocaleString()}`} />
              <Area type="monotone" dataKey="equity" stroke="#10b981" fill="url(#bt)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <p className="text-right text-xs text-muted-foreground">Run ID: {result.id}</p>
    </div>
  );
}
```

- [ ] **Step 2: frontend/components/backtest/backtest-form.tsx 작성**

```tsx
// frontend/components/backtest/backtest-form.tsx
"use client";

import { useState } from "react";
import useSWR from "swr";
import { backtestApi } from "@/lib/api";
import type { BacktestRunOut, StrategyDef } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BacktestResult } from "./backtest-result";

export function BacktestForm() {
  const { data: strategies } = useSWR("/api/backtest/strategies", backtestApi.strategies);

  const [ticker, setTicker] = useState("005930.KS");
  const [strategy, setStrategy] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 3); return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [params, setParams] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestRunOut | null>(null);
  const [error, setError] = useState("");

  const selectedStrategy: StrategyDef | undefined =
    strategies?.find((s) => s.name === strategy) ?? strategies?.[0];

  const run = async () => {
    if (!selectedStrategy) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const parsedParams = Object.fromEntries(
        Object.entries(selectedStrategy.params_schema).map(([k, schema]) => [
          k, parseFloat(params[k] ?? String(schema.default)),
        ])
      );
      const res = await backtestApi.run({
        ticker,
        strategy: selectedStrategy.name,
        params: parsedParams,
        period_start: startDate,
        period_end: endDate,
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle className="text-base">파라미터 설정</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <Label>티커 (yfinance)</Label>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="005930.KS" />
            </div>
            <div className="space-y-1">
              <Label>전략</Label>
              <Select value={strategy || selectedStrategy?.name || ""}
                onValueChange={setStrategy}>
                <SelectTrigger><SelectValue placeholder="전략 선택" /></SelectTrigger>
                <SelectContent>
                  {strategies?.map((s) => (
                    <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>시작일</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>종료일</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          {selectedStrategy && (
            <div className="flex flex-wrap gap-4">
              {Object.entries(selectedStrategy.params_schema).map(([k, schema]) => (
                <div key={k} className="space-y-1">
                  <Label>{schema.label}</Label>
                  <Input
                    type="number"
                    value={params[k] ?? String(schema.default)}
                    onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                    min={schema.min} max={schema.max}
                    className="w-24"
                  />
                </div>
              ))}
            </div>
          )}

          <Button onClick={run} disabled={running || !strategies}>
            {running ? "실행 중…" : "백테스트 실행"}
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && <BacktestResult result={result} />}
    </div>
  );
}
```

- [ ] **Step 3: frontend/app/backtest/page.tsx 작성**

```tsx
// frontend/app/backtest/page.tsx
import { BacktestForm } from "@/components/backtest/backtest-form";

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">백테스트 (SMA Crossover)</h1>
      <BacktestForm />
    </div>
  );
}
```

- [ ] **Step 4: 빌드 + 타입 확인**

```bash
cd frontend && npx tsc --noEmit && npm run build 2>&1 | tail -10
```

Expected: 타입 오류 없음, 빌드 성공

- [ ] **Step 5: commit**

```bash
git add frontend/app/backtest/ frontend/components/backtest/
git commit -m "feat: backtest page with SMA form + equity curve result"
```

---

## Task 13: 배포 설정 검증

**Files:**
- Review: `Dockerfile`, `render.yaml`
- Create: `frontend/vercel.json`

- [ ] **Step 1: vercel.json 생성**

`frontend/vercel.json`:

```json
{
  "env": {
    "API_URL": "@dudunomics-api-url"
  }
}
```

Vercel 대시보드에서 `dudunomics-api-url` 환경변수 시크릿을 Render API URL로 설정.

- [ ] **Step 2: Docker 빌드 테스트**

```bash
docker build -t dudunomics-api . 2>&1 | tail -5
```

Expected: `Successfully built ...`

- [ ] **Step 3: 로컬 통합 테스트 — API + Frontend 동시 기동**

터미널 1:
```bash
uv run uvicorn api.main:app --port 8000 --reload
```

터미널 2:
```bash
cd frontend && npm run dev
```

브라우저에서 `http://localhost:3000` 접속 → `/portfolio`로 리다이렉트 확인

- [ ] **Step 4: E2E 체크리스트**

다음을 브라우저에서 직접 확인:
- [ ] `/portfolio` 페이지 로드 (빈 보유 종목 상태)
- [ ] `/holdings` 에서 `005930.KS` + `AAPL` 추가 → 저장
- [ ] `/portfolio` 에서 30초 뒤 갱신, KPI 카드 표시
- [ ] KRW ↔ USD 토글 동작
- [ ] `/backtest` 에서 `AAPL` 3년 SMA(5,20) 실행 → 결과 차트 표시
- [ ] API docs `http://localhost:8000/docs` 접속 확인

- [ ] **Step 5: 최종 테스트 실행**

```bash
uv run pytest tests/ -v
```

Expected: 모든 테스트 PASSED

- [ ] **Step 6: 최종 commit**

```bash
git add frontend/vercel.json
git commit -m "chore: add Vercel config for frontend deployment"
```

---

## 플랜 Self-Review

### Spec Coverage

| 요구사항 | 구현 Task |
|---|---|
| Dash 제거 → FastAPI | Task 1, 6 |
| Next.js 15 App Router | Task 7 |
| Holdings CRUD API | Task 3 |
| Portfolio current/history API | Task 4 |
| FX + Backtest API | Task 5 |
| TypeScript 타입 + API client | Task 8 |
| Navigation + Layout | Task 9 |
| Portfolio 페이지 (KPI, pie, curve, table) | Task 10 |
| Holdings Editor 페이지 | Task 11 |
| Backtest 페이지 | Task 12 |
| Render + Vercel 배포 | Task 13 |
| SMA 전략 (기존 core 유지) | core 그대로 |
| APScheduler snapshot_job | core 그대로 |

### 누락 없음 확인
- `HoldingOut`에 `updated_at` 필드 있음 → `datetime` 타입으로 `conftest.py` `fresh_db` 픽스처에서 정상 처리
- `holdings-editor.tsx`에서 `initialHoldings` prop 타입과 `HoldingOut` 일치 ✓
- `BacktestRunIn.params` → `dict` (Python) / `Record<string, number>` (TS) — backtest.py에서 `body.params`는 dict이고 라우터가 직접 전달 ✓
