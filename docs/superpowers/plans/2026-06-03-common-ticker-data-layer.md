# Common Ticker Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a common ticker data layer so portfolio, watchlist, growth, screener, and stock search read shared cached price and fundamental data instead of page-specific ad hoc fetches.

**Architecture:** Add shared repository tables for ticker profiles, fundamental snapshots, and data status, then introduce `core/data/ticker_data_service.py` as the single read/hydrate entry point. Keep UI read APIs cache-only and restrict external fetches to explicit hydrate/batch flows. Promote the Terminal lightweight chart into a shared chart component and use it from a new `/stocks` ticker hub and Watchlist details.

**Tech Stack:** Python/FastAPI/DuckDB/SQLAlchemy/Pandas on the backend; Next.js 16.2.6/TypeScript/SWR/lightweight-charts on the frontend; pytest and ESLint for verification.

---

## Current Constraints

- The worktree is dirty. Do not revert unrelated existing changes.
- Natural-language output must stay Korean.
- Manual file edits use `apply_patch`.
- UI verification must use the in-app browser for local pages when possible.
- OHLCV policy: KIS-first, no yfinance in the v1 OHLCV default path.
- General read APIs must be cache-only. Only hydrate endpoints and batch jobs may call external sources.

## File Map

- Modify `core/repository.py`: add schema and repository helpers for `ticker_profiles`, `fundamental_snapshots`, and `ticker_data_status`.
- Create `core/data/ticker_data_service.py`: shared ticker overview, price history, fundamentals, data status, and hydrate functions.
- Create `api/routers/tickers.py`: `/api/tickers/{ticker}/overview` and `/api/tickers/{ticker}/hydrate`.
- Modify `api/main.py`: include tickers router.
- Modify `api/models.py`: add ticker overview/status/hydrate response models.
- Modify `api/routers/growth.py`: delegate valuation/hydrate reads to the common service where possible.
- Modify `api/routers/candles.py`: keep cache-only and eventually delegate to common service.
- Create `frontend/components/charts/ticker-candle-chart.tsx`: shared lightweight chart.
- Modify `frontend/components/terminal/widgets/CandleChart.tsx`: wrap/reuse shared chart.
- Create `frontend/components/stocks/ticker-detail.tsx`: common ticker detail panel.
- Create `frontend/app/stocks/page.tsx`: ticker hub page.
- Modify `frontend/app/watchlist/page.tsx`: use common ticker detail panel.
- Modify `frontend/components/nav.tsx`: add stocks route.
- Modify `frontend/lib/api.ts` and `frontend/lib/types.ts`: add ticker API client and types.
- Tests:
  - `tests/test_common_ticker_repository.py`
  - `tests/test_ticker_data_service.py`
  - `tests/test_tickers_api.py`
  - update `tests/test_growth_api.py`, `tests/test_candles_api.py`, `tests/test_watchlists_api.py` as needed.

---

### Task 1: Shared Data Schema And Repository

**Files:**
- Modify: `core/repository.py`
- Create: `tests/test_common_ticker_repository.py`

- [ ] **Step 1: Write repository tests**

Create `tests/test_common_ticker_repository.py` with these behaviors:

```python
from datetime import date, datetime

import pytest

import core.repository as repo_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(repo_module, "DB_PATH", db_path)
    repo_module._engine = None
    yield
    if repo_module._engine is not None:
        repo_module._engine.dispose()
    repo_module._engine = None


def test_upsert_and_get_ticker_profile():
    import core.repository as repo

    repo.upsert_ticker_profile({
        "ticker": "BE",
        "name": "Bloom Energy Corporation",
        "market": "US",
        "country": "USA",
        "currency": "USD",
        "sector": "Technology",
        "industry": "Electrical Equipment",
        "exchange": "NYSE",
        "source": "test",
    })

    profile = repo.get_ticker_profile("BE")
    assert profile["ticker"] == "BE"
    assert profile["name"] == "Bloom Energy Corporation"
    assert profile["exchange"] == "NYSE"
    assert profile["updated_at"] is not None


def test_upsert_and_get_latest_fundamental_snapshot():
    import core.repository as repo

    repo.upsert_fundamental_snapshot({
        "ticker": "BE",
        "as_of": date(2026, 6, 3),
        "source": "finviz",
        "per": None,
        "pbr": 12.3,
        "psr": 35.1,
        "peg": 0.6,
        "forward_pe": 69.47,
        "trailing_pe": None,
        "forward_eps": 104.03,
        "eps_ttm": None,
        "roe": None,
        "roic": None,
        "debt_ratio": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": 82.2,
        "eps_growth": None,
        "market_cap": None,
        "raw_json": {"hello": "world"},
    })

    snapshot = repo.get_latest_fundamental_snapshot("BE")
    assert snapshot["ticker"] == "BE"
    assert snapshot["source"] == "finviz"
    assert snapshot["peg"] == 0.6
    assert snapshot["raw_json"]["hello"] == "world"


def test_upsert_and_get_ticker_data_status():
    import core.repository as repo

    repo.upsert_ticker_data_status({
        "ticker": "BE",
        "data_type": "ohlcv",
        "source": "kis",
        "min_date": date(2025, 6, 1),
        "max_date": date(2026, 6, 3),
        "last_fetched_at": datetime(2026, 6, 3, 10, 0, 0),
        "last_success_at": datetime(2026, 6, 3, 10, 0, 0),
        "last_error": None,
        "coverage_json": {"rows": 252},
    })

    statuses = repo.get_ticker_data_status("BE")
    assert len(statuses) == 1
    assert statuses[0]["data_type"] == "ohlcv"
    assert statuses[0]["coverage_json"]["rows"] == 252
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_common_ticker_repository.py -q
```

Expected: fail because repository functions/tables do not exist.

- [ ] **Step 3: Add schema**

In `core/repository.py` `_init_schema`, add:

```sql
CREATE TABLE IF NOT EXISTS ticker_profiles (
    ticker     TEXT PRIMARY KEY,
    name       TEXT,
    market     TEXT,
    country    TEXT,
    currency   TEXT,
    sector     TEXT,
    industry   TEXT,
    exchange   TEXT,
    source     TEXT,
    updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS fundamental_snapshots (
    ticker           TEXT NOT NULL,
    as_of            DATE NOT NULL,
    source           TEXT NOT NULL,
    per              DOUBLE,
    pbr              DOUBLE,
    psr              DOUBLE,
    peg              DOUBLE,
    forward_pe       DOUBLE,
    trailing_pe      DOUBLE,
    forward_eps      DOUBLE,
    eps_ttm          DOUBLE,
    roe              DOUBLE,
    roic             DOUBLE,
    debt_ratio       DOUBLE,
    current_ratio    DOUBLE,
    gross_margin     DOUBLE,
    operating_margin DOUBLE,
    revenue_growth   DOUBLE,
    eps_growth       DOUBLE,
    market_cap       DOUBLE,
    raw_json         JSON,
    fetched_at       TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (ticker, as_of, source)
);

CREATE TABLE IF NOT EXISTS ticker_data_status (
    ticker          TEXT NOT NULL,
    data_type       TEXT NOT NULL,
    source          TEXT NOT NULL,
    min_date        DATE,
    max_date        DATE,
    last_fetched_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_error      TEXT,
    coverage_json   JSON,
    PRIMARY KEY (ticker, data_type, source)
);
```

Also add matching `CREATE TABLE IF NOT EXISTS ...` entries to the migration list for compatibility.

- [ ] **Step 4: Add repository helpers**

Add functions near existing cache helpers:

```python
def upsert_ticker_profile(row: dict) -> None:
    row = normalize_finite_numbers(row)
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_profiles
                (ticker, name, market, country, currency, sector, industry, exchange, source, updated_at)
            VALUES
                (:ticker, :name, :market, :country, :currency, :sector, :industry, :exchange, :source, current_timestamp)
            ON CONFLICT (ticker) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                country = excluded.country,
                currency = excluded.currency,
                sector = excluded.sector,
                industry = excluded.industry,
                exchange = excluded.exchange,
                source = excluded.source,
                updated_at = current_timestamp
        """), row)
        s.commit()


def get_ticker_profile(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT ticker, name, market, country, currency, sector, industry, exchange, source, updated_at
            FROM ticker_profiles
            WHERE ticker = :ticker
        """), {"ticker": ticker.upper()}).mappings().fetchone()
    return dict(row) if row else None


def upsert_fundamental_snapshot(row: dict) -> None:
    row = normalize_finite_numbers({**row, "raw_json": json.dumps(row.get("raw_json") or {})})
    with session() as s:
        s.execute(text("""
            INSERT INTO fundamental_snapshots
                (ticker, as_of, source, per, pbr, psr, peg, forward_pe, trailing_pe,
                 forward_eps, eps_ttm, roe, roic, debt_ratio, current_ratio, gross_margin,
                 operating_margin, revenue_growth, eps_growth, market_cap, raw_json, fetched_at)
            VALUES
                (:ticker, :as_of, :source, :per, :pbr, :psr, :peg, :forward_pe, :trailing_pe,
                 :forward_eps, :eps_ttm, :roe, :roic, :debt_ratio, :current_ratio, :gross_margin,
                 :operating_margin, :revenue_growth, :eps_growth, :market_cap, :raw_json, current_timestamp)
            ON CONFLICT (ticker, as_of, source) DO UPDATE SET
                per = excluded.per,
                pbr = excluded.pbr,
                psr = excluded.psr,
                peg = excluded.peg,
                forward_pe = excluded.forward_pe,
                trailing_pe = excluded.trailing_pe,
                forward_eps = excluded.forward_eps,
                eps_ttm = excluded.eps_ttm,
                roe = excluded.roe,
                roic = excluded.roic,
                debt_ratio = excluded.debt_ratio,
                current_ratio = excluded.current_ratio,
                gross_margin = excluded.gross_margin,
                operating_margin = excluded.operating_margin,
                revenue_growth = excluded.revenue_growth,
                eps_growth = excluded.eps_growth,
                market_cap = excluded.market_cap,
                raw_json = excluded.raw_json,
                fetched_at = current_timestamp
        """), row)
        s.commit()


def get_latest_fundamental_snapshot(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT *
            FROM fundamental_snapshots
            WHERE ticker = :ticker
            ORDER BY as_of DESC, fetched_at DESC
            LIMIT 1
        """), {"ticker": ticker.upper()}).mappings().fetchone()
    if not row:
        return None
    result = dict(row)
    raw = result.get("raw_json")
    if isinstance(raw, str):
        result["raw_json"] = json.loads(raw)
    return result


def upsert_ticker_data_status(row: dict) -> None:
    row = normalize_finite_numbers({**row, "coverage_json": json.dumps(row.get("coverage_json") or {})})
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_data_status
                (ticker, data_type, source, min_date, max_date, last_fetched_at,
                 last_success_at, last_error, coverage_json)
            VALUES
                (:ticker, :data_type, :source, :min_date, :max_date, :last_fetched_at,
                 :last_success_at, :last_error, :coverage_json)
            ON CONFLICT (ticker, data_type, source) DO UPDATE SET
                min_date = excluded.min_date,
                max_date = excluded.max_date,
                last_fetched_at = excluded.last_fetched_at,
                last_success_at = excluded.last_success_at,
                last_error = excluded.last_error,
                coverage_json = excluded.coverage_json
        """), row)
        s.commit()


def get_ticker_data_status(ticker: str) -> list[dict]:
    with session() as s:
        rows = s.execute(text("""
            SELECT *
            FROM ticker_data_status
            WHERE ticker = :ticker
            ORDER BY data_type, source
        """), {"ticker": ticker.upper()}).mappings().fetchall()
    result = []
    for row in rows:
        item = dict(row)
        raw = item.get("coverage_json")
        if isinstance(raw, str):
            item["coverage_json"] = json.loads(raw)
        result.append(item)
    return result
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
uv run pytest tests/test_common_ticker_repository.py -q
```

Expected: all pass.

---

### Task 2: TickerDataService Core

**Files:**
- Create: `core/data/ticker_data_service.py`
- Create: `tests/test_ticker_data_service.py`

- [ ] **Step 1: Write service tests**

Create `tests/test_ticker_data_service.py`:

```python
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

import core.repository as repo_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(repo_module, "DB_PATH", db_path)
    repo_module._engine = None
    yield
    if repo_module._engine is not None:
        repo_module._engine.dispose()
    repo_module._engine = None


def _fake_prices(ticker="BE"):
    idx = pd.date_range("2026-01-02", periods=3, freq="B")
    frame = pd.DataFrame({
        "Open": [10.0, 11.0, 12.0],
        "High": [11.0, 12.0, 13.0],
        "Low": [9.0, 10.0, 11.0],
        "Close": [10.5, 11.5, 12.5],
        "Volume": [100, 120, 130],
    }, index=idx)
    return pd.concat({ticker: frame}, axis=1)


def test_get_price_history_is_cache_only():
    from core.data import ticker_data_service as svc

    with patch("core.data.ticker_data_service.fetch_ohlcv", return_value=(_fake_prices("BE"), [])) as fetch:
        out = svc.get_price_history("BE", date(2026, 1, 1), date(2026, 1, 10))

    fetch.assert_called_once_with(["BE"], date(2026, 1, 1), date(2026, 1, 10), cache_only=True)
    assert out["ticker"] == "BE"
    assert len(out["candles"]) == 3
    assert out["candles"][0]["time"] == "2026-01-02"


def test_get_fundamentals_prefers_snapshot_then_quant_score():
    import core.repository as repo
    from core.data import ticker_data_service as svc

    repo.upsert_fundamental_snapshot({
        "ticker": "BE",
        "as_of": date(2026, 6, 3),
        "source": "finviz",
        "per": None,
        "pbr": 12.3,
        "psr": 35.1,
        "peg": 0.6,
        "forward_pe": 69.47,
        "trailing_pe": None,
        "forward_eps": 104.03,
        "eps_ttm": None,
        "roe": None,
        "roic": None,
        "debt_ratio": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": 82.2,
        "eps_growth": None,
        "market_cap": None,
        "raw_json": {},
    })

    result = svc.get_fundamentals("BE", universe="sp500")
    assert result["ticker"] == "BE"
    assert result["valuation_source"] == "finviz"
    assert result["peg"] == 0.6
    assert result["forward_revenue_growth"] == 82.2


def test_hydrate_ohlcv_updates_status():
    from core.data import ticker_data_service as svc
    import core.repository as repo

    with patch("core.data.ticker_data_service.fetch_ohlcv", return_value=(_fake_prices("BE"), [])):
        result = svc.hydrate_ticker_data("BE", scopes=["ohlcv"])

    assert result["ticker"] == "BE"
    assert result["warnings"] == []
    statuses = repo.get_ticker_data_status("BE")
    assert statuses[0]["data_type"] == "ohlcv"
    assert statuses[0]["coverage_json"]["rows"] == 3
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_ticker_data_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Implement service**

Create `core/data/ticker_data_service.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from core import repository as repo
from core.data.normalization import normalize_finite_numbers
from core.data.ohlcv_cache import fetch_ohlcv


def get_price_history(ticker: str, start: date, end: date) -> dict:
    ticker = ticker.upper()
    prices, warnings = fetch_ohlcv([ticker], start, end, cache_only=True)
    candles = []
    if not prices.empty and ticker in prices.columns.get_level_values(0):
        df = prices[ticker][["Open", "High", "Low", "Close", "Volume"]].dropna()
        candles = [
            {
                "time": ts.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
            for ts, row in df.iterrows()
        ]
    return {"ticker": ticker, "start": start, "end": end, "candles": candles, "warnings": warnings}


def get_fundamentals(ticker: str, universe: str = "sp500") -> dict:
    ticker = ticker.upper()
    snapshot = repo.get_latest_fundamental_snapshot(ticker)
    if snapshot:
        return normalize_finite_numbers({
            "ticker": ticker,
            "universe": universe,
            "valuation_source": snapshot.get("source"),
            "valuation_as_of": snapshot.get("as_of"),
            "peg": snapshot.get("peg"),
            "forward_pe": snapshot.get("forward_pe"),
            "psr": snapshot.get("psr"),
            "forward_eps": snapshot.get("forward_eps"),
            "forward_revenue_growth": snapshot.get("revenue_growth"),
            "forward_eps_growth": snapshot.get("eps_growth"),
            "pbr": snapshot.get("pbr"),
            "per": snapshot.get("per"),
            "roe": snapshot.get("roe"),
            "roic": snapshot.get("roic"),
            "market_cap": snapshot.get("market_cap"),
            "fallback_used": True,
        })

    row = repo.get_quant_ticker(ticker, universe)
    return normalize_finite_numbers({
        "ticker": ticker,
        "universe": universe,
        "valuation_source": "BATCH" if row else None,
        "valuation_as_of": row.get("as_of") if row else None,
        "peg": row.get("raw_peg") if row else None,
        "forward_pe": row.get("raw_fwd_pe") if row else None,
        "psr": row.get("raw_psr") if row else None,
        "forward_eps": row.get("raw_fwd_eps") if row else None,
        "forward_revenue_growth": row.get("raw_fwd_rev_growth") if row else None,
        "forward_eps_growth": row.get("raw_fwd_eps_growth") if row else None,
        "pbr": row.get("raw_pbr") if row else None,
        "per": row.get("raw_trailing_pe") if row else None,
        "roe": row.get("raw_roe") if row else None,
        "roic": row.get("raw_roic") if row else None,
        "market_cap": row.get("raw_market_cap_usd_m") if row else None,
        "fallback_used": False,
    })


def get_data_status(ticker: str) -> list[dict]:
    return repo.get_ticker_data_status(ticker.upper())


def hydrate_ticker_data(ticker: str, scopes: list[str] | None = None) -> dict:
    ticker = ticker.upper()
    scopes = scopes or ["ohlcv"]
    warnings: list[str] = []
    if "ohlcv" in scopes:
        today = date.today()
        start = today - timedelta(days=420)
        prices, fetch_warnings = fetch_ohlcv([ticker], start, today, force=True)
        warnings.extend(fetch_warnings)
        _update_ohlcv_status(ticker, prices, fetch_warnings)
    return {"ticker": ticker, "scopes": scopes, "warnings": warnings, "status": get_data_status(ticker)}


def _update_ohlcv_status(ticker: str, prices: pd.DataFrame, warnings: list[str]) -> None:
    now = datetime.now()
    min_date = None
    max_date = None
    rows = 0
    if not prices.empty and ticker in prices.columns.get_level_values(0):
        frame = prices[ticker].dropna(how="all")
        if not frame.empty:
            min_date = frame.index.min().date()
            max_date = frame.index.max().date()
            rows = len(frame)
    repo.upsert_ticker_data_status({
        "ticker": ticker,
        "data_type": "ohlcv",
        "source": "kis",
        "min_date": min_date,
        "max_date": max_date,
        "last_fetched_at": now,
        "last_success_at": now if rows else None,
        "last_error": "; ".join(warnings) if warnings else None,
        "coverage_json": {"rows": rows},
    })
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/test_ticker_data_service.py tests/test_common_ticker_repository.py -q
```

Expected: all pass.

---

### Task 3: Tickers API

**Files:**
- Modify: `api/models.py`
- Create: `api/routers/tickers.py`
- Modify: `api/main.py`
- Create: `tests/test_tickers_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/test_tickers_api.py`:

```python
from datetime import date
from unittest.mock import patch

import pytest


@pytest.fixture
def tickers_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "tickers@test.com", "password": "password123"})
    return c


def test_ticker_overview_returns_common_data(tickers_client):
    payload = {
        "ticker": "BE",
        "profile": {"ticker": "BE", "name": "Bloom Energy Corporation"},
        "fundamentals": {"ticker": "BE", "peg": 0.6, "valuation_source": "finviz"},
        "status": [],
    }
    with patch("api.routers.tickers.get_ticker_overview", return_value=payload):
        res = tickers_client.get("/api/tickers/BE/overview")
    assert res.status_code == 200
    assert res.json()["ticker"] == "BE"
    assert res.json()["fundamentals"]["peg"] == 0.6


def test_ticker_hydrate_delegates_scopes(tickers_client):
    payload = {"ticker": "BE", "scopes": ["ohlcv"], "warnings": [], "status": []}
    with patch("api.routers.tickers.hydrate_ticker_data", return_value=payload) as hydrate:
        res = tickers_client.post("/api/tickers/BE/hydrate?scopes=ohlcv")
    assert res.status_code == 200
    assert res.json()["ticker"] == "BE"
    hydrate.assert_called_once_with("BE", scopes=["ohlcv"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_tickers_api.py -q
```

Expected: fail because router/models do not exist.

- [ ] **Step 3: Add models**

In `api/models.py`, add:

```python
class TickerDataStatusOut(BaseModel):
    ticker: str
    data_type: str
    source: str
    min_date: date | None = None
    max_date: date | None = None
    last_fetched_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    coverage_json: dict = Field(default_factory=dict)


class TickerOverviewOut(BaseModel):
    ticker: str
    profile: dict | None = None
    fundamentals: dict | None = None
    status: list[TickerDataStatusOut] = Field(default_factory=list)


class TickerHydrateOut(BaseModel):
    ticker: str
    scopes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: list[TickerDataStatusOut] = Field(default_factory=list)
```

- [ ] **Step 4: Add router**

Create `api/routers/tickers.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.models import TickerHydrateOut, TickerOverviewOut
from core.auth.deps import CurrentUser, current_user
from core.data.ticker_data_service import (
    get_data_status,
    get_fundamentals,
    hydrate_ticker_data,
)
from core import repository as repo


router = APIRouter(prefix="/api/tickers", tags=["tickers"])


def get_ticker_overview(ticker: str, universe: str = "sp500") -> dict:
    ticker = ticker.upper()
    return {
        "ticker": ticker,
        "profile": repo.get_ticker_profile(ticker),
        "fundamentals": get_fundamentals(ticker, universe=universe),
        "status": get_data_status(ticker),
    }


@router.get("/{ticker}/overview", response_model=TickerOverviewOut)
def ticker_overview(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    return get_ticker_overview(ticker, universe=universe)


@router.post("/{ticker}/hydrate", response_model=TickerHydrateOut)
def ticker_hydrate(
    ticker: str,
    scopes: list[str] = Query(default=["ohlcv"]),
    user: CurrentUser = Depends(current_user),
):
    return hydrate_ticker_data(ticker.upper(), scopes=scopes)
```

In `api/main.py`, include:

```python
from api.routers.tickers import router as tickers_router
app.include_router(tickers_router)
```

- [ ] **Step 5: Run API tests**

Run:

```bash
uv run pytest tests/test_tickers_api.py tests/test_ticker_data_service.py -q
```

Expected: all pass.

---

### Task 4: Growth Valuation Reads Common Fundamentals

**Files:**
- Modify: `api/routers/growth.py`
- Modify: `tests/test_growth_api.py`

- [ ] **Step 1: Add regression test**

In `tests/test_growth_api.py`, add a test that inserts a `fundamental_snapshot` for ticker `BE`, then calls `/api/growth/ticker/BE/valuation?universe=sp500` and asserts the response uses snapshot values without needing a quant score.

Test body:

```python
def test_growth_valuation_uses_common_fundamental_snapshot(growth_client):
    import core.repository as repo
    from datetime import date

    repo.upsert_fundamental_snapshot({
        "ticker": "BE",
        "as_of": date(2026, 6, 3),
        "source": "finviz",
        "per": None,
        "pbr": 12.3,
        "psr": 35.1,
        "peg": 0.6,
        "forward_pe": 69.47,
        "trailing_pe": None,
        "forward_eps": 104.03,
        "eps_ttm": None,
        "roe": None,
        "roic": None,
        "debt_ratio": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": 82.2,
        "eps_growth": None,
        "market_cap": None,
        "raw_json": {},
    })

    res = growth_client.get("/api/growth/ticker/BE/valuation?universe=sp500")
    assert res.status_code == 200
    data = res.json()
    assert data["peg"] == 0.6
    assert data["forward_pe"] == 69.47
    assert data["valuation_source"] == "finviz"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/test_growth_api.py::test_growth_valuation_uses_common_fundamental_snapshot -q
```

Expected: fail until growth valuation consults common service.

- [ ] **Step 3: Update growth valuation**

In `api/routers/growth.py`, import:

```python
from core.data.ticker_data_service import get_fundamentals
```

At the top of the valuation endpoint, call `common = get_fundamentals(ticker, universe=universe)`. If `common["valuation_source"]` is not `None`, return those values in the existing `GrowthValuationOut` shape, preserving existing price target consensus logic.

- [ ] **Step 4: Run growth tests**

Run:

```bash
uv run pytest tests/test_growth_api.py tests/test_ticker_data_service.py -q
```

Expected: all pass.

---

### Task 5: Shared Lightweight Chart Component

**Files:**
- Create: `frontend/components/charts/ticker-candle-chart.tsx`
- Modify: `frontend/components/terminal/widgets/CandleChart.tsx`

- [ ] **Step 1: Create shared chart component**

Create `frontend/components/charts/ticker-candle-chart.tsx` by moving the chart implementation from `frontend/components/terminal/widgets/CandleChart.tsx`. Keep props:

```ts
interface Props {
  ticker: string;
  defaultPeriod?: "5D" | "1M" | "3M" | "6M" | "1Y";
  defaultShowIndicators?: boolean;
  refreshKey?: number;
  heightClassName?: string;
}
```

Use `defaultPeriod ?? "3M"` and `defaultShowIndicators ?? false`.

- [ ] **Step 2: Wrap Terminal chart**

Replace the old Terminal widget body with:

```tsx
"use client";

import { TickerCandleChart } from "@/components/charts/ticker-candle-chart";

interface Props { ticker: string }

export function CandleChart({ ticker }: Props) {
  return <TickerCandleChart ticker={ticker} defaultPeriod="3M" heightClassName="h-full" />;
}
```

- [ ] **Step 3: Run frontend lint**

Run:

```bash
cd frontend && npm run lint -- components/charts/ticker-candle-chart.tsx components/terminal/widgets/CandleChart.tsx
```

Expected: no lint errors.

---

### Task 6: Stocks Hub Page

**Files:**
- Create: `frontend/components/stocks/ticker-detail.tsx`
- Create: `frontend/app/stocks/page.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/nav.tsx`

- [ ] **Step 1: Add frontend types**

In `frontend/lib/types.ts`, add:

```ts
export interface TickerDataStatus {
  ticker: string;
  data_type: string;
  source: string;
  min_date: string | null;
  max_date: string | null;
  last_fetched_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  coverage_json: Record<string, unknown>;
}

export interface TickerOverview {
  ticker: string;
  profile: Record<string, unknown> | null;
  fundamentals: Record<string, unknown> | null;
  status: TickerDataStatus[];
}

export interface TickerHydrate {
  ticker: string;
  scopes: string[];
  warnings: string[];
  status: TickerDataStatus[];
}
```

- [ ] **Step 2: Add frontend API**

In `frontend/lib/api.ts`, add:

```ts
export const tickersApi = {
  overview: (ticker: string, universe = "sp500") =>
    request<TickerOverview>(`/api/tickers/${encodeURIComponent(ticker)}/overview?universe=${encodeURIComponent(universe)}`),
  hydrate: (ticker: string, scopes = ["ohlcv"]) =>
    request<TickerHydrate>(
      `/api/tickers/${encodeURIComponent(ticker)}/hydrate?${scopes.map((scope) => `scopes=${encodeURIComponent(scope)}`).join("&")}`,
      { method: "POST" },
    ),
};
```

- [ ] **Step 3: Create ticker detail component**

Create `frontend/components/stocks/ticker-detail.tsx` that renders:

- ticker/name
- data status list
- `TickerCandleChart`
- existing `ValuationCard`
- existing `TimingCard`
- hydrate button that calls `tickersApi.hydrate(ticker, ["ohlcv", "fundamental"])`

- [ ] **Step 4: Create `/stocks` page**

Create `frontend/app/stocks/page.tsx` with:

- search input
- search button
- selected ticker state
- `TickerDetail` when selected

- [ ] **Step 5: Add nav link**

In `frontend/components/nav.tsx`, add:

```ts
{ href: "/stocks", label: "종목검색" }
```

- [ ] **Step 6: Run frontend lint**

Run:

```bash
cd frontend && npm run lint -- app/stocks/page.tsx components/stocks/ticker-detail.tsx components/nav.tsx lib/api.ts lib/types.ts
```

Expected: no lint errors.

---

### Task 7: Watchlist Uses Common Ticker Detail

**Files:**
- Modify: `frontend/app/watchlist/page.tsx`
- Modify: `frontend/components/stocks/ticker-detail.tsx`

- [ ] **Step 1: Add compact mode to ticker detail**

Update `TickerDetail` props:

```ts
interface TickerDetailProps {
  ticker: string;
  universe?: string;
  name?: string | null;
  compact?: boolean;
}
```

If `compact` is true, do not render the search header. Keep chart, valuation, timing, and data status.

- [ ] **Step 2: Replace Watchlist detail panel**

In `frontend/app/watchlist/page.tsx`, replace the inline chart/valuation/timing detail section with:

```tsx
<TickerDetail
  ticker={detailTicker}
  universe={detailUniverse}
  name={selectedItem?.name}
  compact
/>
```

Keep the Performance View and Watchlist management UI unchanged.

- [ ] **Step 3: Run frontend lint**

Run:

```bash
cd frontend && npm run lint -- app/watchlist/page.tsx components/stocks/ticker-detail.tsx
```

Expected: no lint errors.

---

### Task 8: Verification

**Files:**
- No new files unless tests reveal a defect.

- [ ] **Step 1: Backend tests**

Run:

```bash
uv run pytest \
  tests/test_common_ticker_repository.py \
  tests/test_ticker_data_service.py \
  tests/test_tickers_api.py \
  tests/test_growth_api.py \
  tests/test_candles_api.py \
  tests/test_watchlists_api.py \
  tests/test_ohlcv_cache.py \
  tests/test_kis_ohlcv.py \
  -q
```

Expected: all pass.

- [ ] **Step 2: Frontend lint**

Run:

```bash
cd frontend && npm run lint -- \
  app/stocks/page.tsx \
  app/watchlist/page.tsx \
  components/stocks/ticker-detail.tsx \
  components/charts/ticker-candle-chart.tsx \
  components/terminal/widgets/CandleChart.tsx \
  components/nav.tsx \
  lib/api.ts \
  lib/types.ts
```

Expected: no lint errors.

- [ ] **Step 3: Diff check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Browser verification**

Use the in-app browser.

1. Open `http://localhost:3333/stocks`.
2. Search `BE`.
3. Confirm the page shows ticker header, data status, chart area, valuation card, timing card, and hydrate button.
4. Open `http://localhost:3333/watchlist`.
5. Select a Watchlist item.
6. Confirm the detail area uses the same chart/valuation/timing/data status layout.
7. Confirm chart read does not trigger external fetch; only hydrate button triggers data 보강.

Expected: no infinite loading; missing data displays a reason/status.

---

## Self-Review

Spec coverage:

- Shared DB layer: Task 1.
- Shared service: Task 2.
- Cache-only read and hydrate split: Tasks 2, 3, 4.
- Common chart from Terminal: Task 5.
- `/stocks` ticker hub: Task 6.
- Watchlist shared detail: Task 7.
- Verification: Task 8.

Intentionally deferred:

- price target consensus cache.
- FMP-centered collection.
- yfinance OHLCV restoration.
- full Terminal removal.
- portfolio trade/holding redesign.

No placeholders remain. Type names are consistent across backend and frontend tasks.
