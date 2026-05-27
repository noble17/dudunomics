# OHLCV DuckDB Cache Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** yfinance OHLCV 요청을 DuckDB `prices_cache` 테이블로 캐시해서, 같은 구간 재요청 시 네트워크 호출 없이 DB에서 직접 읽도록 한다.

**Architecture:** `core/data/ohlcv_cache.py` 신규 모듈이 캐시 로직을 전담한다. `repository.py`에 DB read/write 함수 2개를 추가하고, `prices_provider.py`와 `index_provider.py`가 내부적으로 이 모듈을 호출하도록 교체한다. 기존 호출부(`backtest.py` 등)는 수정 없음.

**Tech Stack:** Python 3.12, DuckDB 1.2.2, SQLAlchemy 2.0, yfinance 0.2.54, pandas 2.2.3, pytest 8.3.5

---

### Task 1: `repository.py` — DB 함수 2개 추가

**Files:**
- Modify: `core/repository.py` (끝에 추가)
- Test: `tests/test_ohlcv_cache.py` (신규)

- [ ] **Step 1: 테스트 파일 작성 (실패 확인용)**

`tests/test_ohlcv_cache.py` 신규 생성:

```python
import pytest
from datetime import date
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


def test_get_ohlcv_range_empty():
    import core.repository as repo
    assert repo.get_ohlcv_range("AAPL") is None


def test_upsert_and_get_ohlcv_range():
    import core.repository as repo
    rows = [
        {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000},
        {"ticker": "AAPL", "date": date(2023, 1, 3), "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 1200000},
    ]
    repo.upsert_ohlcv_rows(rows)
    result = repo.get_ohlcv_range("AAPL")
    assert result == (date(2023, 1, 2), date(2023, 1, 3))


def test_upsert_ohlcv_rows_ignores_duplicate():
    import core.repository as repo
    row = {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000}
    repo.upsert_ohlcv_rows([row])
    repo.upsert_ohlcv_rows([row])  # 중복 — 예외 없어야 함
    result = repo.get_ohlcv_range("AAPL")
    assert result == (date(2023, 1, 2), date(2023, 1, 2))


def test_get_ohlcv_range_multiple_tickers():
    import core.repository as repo
    repo.upsert_ohlcv_rows([
        {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ])
    repo.upsert_ohlcv_rows([
        {"ticker": "MSFT", "date": date(2023, 2, 1), "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2},
    ])
    assert repo.get_ohlcv_range("AAPL") == (date(2023, 1, 2), date(2023, 1, 2))
    assert repo.get_ohlcv_range("MSFT") == (date(2023, 2, 1), date(2023, 2, 1))
    assert repo.get_ohlcv_range("TSLA") is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics
.venv/bin/pytest tests/test_ohlcv_cache.py -v 2>&1 | head -30
```

예상 결과: `AttributeError: module 'core.repository' has no attribute 'get_ohlcv_range'`

- [ ] **Step 3: `repository.py` 끝에 함수 추가**

`core/repository.py` 파일 맨 끝에 추가:

```python
# ── OHLCV Cache ───────────────────────────────────────────────────────────────

def get_ohlcv_range(ticker: str) -> "tuple[date, date] | None":
    """캐시된 (min_date, max_date) 반환. 없으면 None."""
    with session() as s:
        row = s.execute(text("""
            SELECT MIN(date), MAX(date) FROM prices_cache WHERE ticker = :ticker
        """), {"ticker": ticker}).fetchone()
        if row is None or row[0] is None:
            return None
        return (row[0], row[1])


def upsert_ohlcv_rows(rows: list[dict]) -> None:
    """(ticker, date, open, high, low, close, volume) 배치 insert. 중복 무시."""
    if not rows:
        return
    with session() as s:
        for row in rows:
            s.execute(text("""
                INSERT OR IGNORE INTO prices_cache (ticker, date, open, high, low, close, volume)
                VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
            """), row)
        s.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_ohlcv_cache.py::test_get_ohlcv_range_empty tests/test_ohlcv_cache.py::test_upsert_and_get_ohlcv_range tests/test_ohlcv_cache.py::test_upsert_ohlcv_rows_ignores_duplicate tests/test_ohlcv_cache.py::test_get_ohlcv_range_multiple_tickers -v
```

예상 결과: 4개 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add core/repository.py tests/test_ohlcv_cache.py
git commit -m "feat: repository에 OHLCV 캐시 DB 함수 추가 (get_ohlcv_range, upsert_ohlcv_rows)"
```

---

### Task 2: `ohlcv_cache.py` — 캐시 모듈 신규 작성

**Files:**
- Create: `core/data/ohlcv_cache.py`
- Test: `tests/test_ohlcv_cache.py` (Task 1 파일에 테스트 추가)

- [ ] **Step 1: 캐시 히트/미스 테스트 추가**

`tests/test_ohlcv_cache.py` 끝에 추가:

```python
import numpy as np
import pandas as pd
from unittest.mock import patch


def _make_fake_single_ticker_df(ticker: str, n: int = 10) -> pd.DataFrame:
    """yfinance가 단일 티커로 반환하는 형태 (MultiIndex 없음)."""
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": [1_000_000] * n,
    }, index=idx)


def test_fetch_ohlcv_cache_miss_calls_yfinance():
    """캐시 없으면 yfinance 호출."""
    from core.data import ohlcv_cache
    fake = _make_fake_single_ticker_df("AAPL")
    with patch("yfinance.download", return_value=fake) as mock_dl:
        prices, warns = ohlcv_cache.fetch_ohlcv(
            ["AAPL"], date(2023, 1, 2), date(2023, 1, 13)
        )
    assert mock_dl.called
    assert not prices.empty
    assert "AAPL" in prices.columns.get_level_values(0)
    assert "Close" in prices["AAPL"].columns


def test_fetch_ohlcv_cache_hit_skips_yfinance():
    """캐시 완전 히트면 yfinance 미호출."""
    import core.repository as repo
    from core.data import ohlcv_cache

    # 캐시 사전 적재 (2023-01-02 ~ 2023-01-13, 10 영업일)
    rows = [
        {"ticker": "AAPL", "date": date(2023, 1, d),
         "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1_000_000}
        for d in [2, 3, 4, 5, 6, 9, 10, 11, 12, 13]
    ]
    repo.upsert_ohlcv_rows(rows)

    with patch("yfinance.download") as mock_dl:
        prices, warns = ohlcv_cache.fetch_ohlcv(
            ["AAPL"], date(2023, 1, 2), date(2023, 1, 13)
        )
    assert not mock_dl.called
    assert not prices.empty


def test_fetch_ohlcv_stores_data_in_cache():
    """fetch 후 같은 요청은 DB에서 읽음."""
    import core.repository as repo
    from core.data import ohlcv_cache

    fake = _make_fake_single_ticker_df("TSLA", n=5)
    call_count = {"n": 0}
    original_download = __import__("yfinance").download

    def counting_download(*a, **kw):
        call_count["n"] += 1
        return fake

    with patch("yfinance.download", side_effect=counting_download):
        ohlcv_cache.fetch_ohlcv(["TSLA"], date(2023, 1, 2), date(2023, 1, 6))

    # 두 번째 요청은 캐시 히트 (yfinance 미호출)
    with patch("yfinance.download") as mock_dl:
        prices, _ = ohlcv_cache.fetch_ohlcv(["TSLA"], date(2023, 1, 2), date(2023, 1, 6))
    assert not mock_dl.called
    assert not prices.empty


def test_fetch_index_cache_miss_calls_yfinance():
    """인덱스 캐시 없으면 yfinance 호출."""
    from core.data import ohlcv_cache
    idx = pd.date_range("2023-01-02", periods=5, freq="B")
    fake = pd.DataFrame({"Close": [100.0] * 5}, index=idx)

    with patch("yfinance.download", return_value=fake) as mock_dl:
        series = ohlcv_cache.fetch_index("SPY", date(2023, 1, 2), date(2023, 1, 6))
    assert mock_dl.called
    assert not series.empty


def test_fetch_index_cache_hit_skips_yfinance():
    """인덱스 캐시 히트면 yfinance 미호출."""
    import core.repository as repo
    from core.data import ohlcv_cache

    rows = [
        {"ticker": "SPY", "date": date(2023, 1, d),
         "open": 400.0, "high": 401.0, "low": 399.0, "close": 400.5, "volume": 5_000_000}
        for d in [2, 3, 4, 5, 6]
    ]
    repo.upsert_ohlcv_rows(rows)

    with patch("yfinance.download") as mock_dl:
        series = ohlcv_cache.fetch_index("SPY", date(2023, 1, 2), date(2023, 1, 6))
    assert not mock_dl.called
    assert not series.empty
    assert series.name == "SPY"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_ohlcv_cache.py::test_fetch_ohlcv_cache_miss_calls_yfinance -v 2>&1 | head -20
```

예상 결과: `ModuleNotFoundError: No module named 'core.data.ohlcv_cache'`

- [ ] **Step 3: `ohlcv_cache.py` 작성**

`core/data/ohlcv_cache.py` 신규 생성:

```python
"""OHLCV DuckDB 캐시 레이어.

fetch_ohlcv / fetch_index 는 DB 우선 조회 → 캐시 미스 시 yfinance fetch 후 저장.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import text

from core import repository as repo

log = logging.getLogger(__name__)

# yfinance exclusive-end + 비영업일 허용 오차 (일수)
_TOLERANCE = timedelta(days=5)


def fetch_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
) -> tuple[pd.DataFrame, list[str]]:
    """tickers OHLCV MultiIndex DataFrame + warnings 반환.

    columns: MultiIndex (ticker, field), field ∈ {Open, High, Low, Close, Volume}
    index: DatetimeIndex tz-naive
    """
    warns: list[str] = []
    if not tickers:
        return pd.DataFrame(), warns

    to_fetch = [t for t in tickers if not _is_cached(t, start, end)]
    if to_fetch:
        warns.extend(_fetch_and_store(to_fetch, start, end))

    return _read_ohlcv(tickers, start, end, warns)


def fetch_index(
    symbol: str,
    start: date,
    end: date,
) -> pd.Series:
    """시장 지수(SPY, ^KS11 등) 종가 시계열 반환 (tz-naive)."""
    if not _is_cached(symbol, start, end):
        _fetch_and_store([symbol], start, end)
    return _read_index(symbol, start, end)


# ── 내부 함수 ─────────────────────────────────────────────────────────────────

def _is_cached(ticker: str, start: date, end: date) -> bool:
    """prices_cache에 [start, end] 구간이 커버되어 있으면 True.

    yfinance exclusive-end 및 비영업일로 인해 실제 저장 날짜가
    요청 날짜와 최대 5일 차이날 수 있으므로 _TOLERANCE 허용.
    """
    cached = repo.get_ohlcv_range(ticker)
    if not cached:
        return False
    min_date, max_date = cached
    return min_date <= start + _TOLERANCE and max_date >= end - _TOLERANCE


def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """yfinance로 데이터 다운로드 후 prices_cache에 저장. warnings 반환."""
    warns: list[str] = []
    try:
        raw = yf.download(
            tickers,
            start=str(start),
            end=str(end),
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        warns.append(f"yfinance fetch 실패 ({tickers}): {e}")
        return warns

    if raw.empty:
        for t in tickers:
            warns.append(f"{t}: 데이터 없음")
        return warns

    if raw.index.tz is not None:
        raw.index = raw.index.tz_localize(None)

    # 단일 티커는 MultiIndex 없이 반환됨 → 수동 변환
    if not isinstance(raw.columns, pd.MultiIndex):
        cols = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        raw.columns = cols
        keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
        raw = raw[keep]
        raw.columns = pd.MultiIndex.from_tuples([(tickers[0], c) for c in raw.columns])
    else:
        sample = raw.columns[0]
        if sample[0] in ("Open", "High", "Low", "Close", "Volume", "Adj Close"):
            raw = raw.swaplevel(axis=1)
        raw = raw.sort_index(axis=1)

    rows: list[dict] = []
    available = raw.columns.get_level_values(0).unique().tolist()
    for ticker in tickers:
        if ticker not in available:
            warns.append(f"{ticker}: 데이터 없음 — 제외")
            continue
        sub = raw[ticker].dropna(how="all")
        if sub.empty:
            warns.append(f"{ticker}: 구간 내 데이터 없음 — 제외")
            continue
        for dt, row in sub.iterrows():
            rows.append({
                "ticker": ticker,
                "date": dt.date(),
                "open": row.get("Open"),
                "high": row.get("High"),
                "low": row.get("Low"),
                "close": row.get("Close"),
                "volume": int(row.get("Volume") or 0),
            })

    repo.upsert_ohlcv_rows(rows)
    return warns


def _read_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
    warns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """prices_cache에서 읽어 MultiIndex(ticker, field) DataFrame 반환."""
    frames: dict[str, pd.DataFrame] = {}
    with repo.session() as s:
        for ticker in tickers:
            rows = s.execute(text("""
                SELECT date, open, high, low, close, volume
                FROM prices_cache
                WHERE ticker = :ticker AND date >= :start AND date <= :end
                ORDER BY date
            """), {"ticker": ticker, "start": start, "end": end}).fetchall()

            if not rows:
                warns.append(f"{ticker}: 캐시에 데이터 없음 — 백테스트에서 제외")
                continue

            idx = pd.to_datetime([r[0] for r in rows])
            frames[ticker] = pd.DataFrame({
                "Open":   [r[1] for r in rows],
                "High":   [r[2] for r in rows],
                "Low":    [r[3] for r in rows],
                "Close":  [r[4] for r in rows],
                "Volume": [r[5] for r in rows],
            }, index=idx)

    if not frames:
        return pd.DataFrame(), warns

    result = pd.concat(frames, axis=1)  # columns: (ticker, field)
    result.index.name = None
    return result.dropna(how="all"), warns


def _read_index(symbol: str, start: date, end: date) -> pd.Series:
    """prices_cache에서 지수 종가 시계열 반환."""
    with repo.session() as s:
        rows = s.execute(text("""
            SELECT date, close FROM prices_cache
            WHERE ticker = :ticker AND date >= :start AND date <= :end
            ORDER BY date
        """), {"ticker": symbol, "start": start, "end": end}).fetchall()

    if not rows:
        log.warning("인덱스 캐시 없음: %s (%s ~ %s)", symbol, start, end)
        return pd.Series(dtype=float, name=symbol)

    return pd.Series(
        [r[1] for r in rows],
        index=pd.to_datetime([r[0] for r in rows]),
        name=symbol,
    )
```

- [ ] **Step 4: 신규 테스트 전체 통과 확인**

```bash
.venv/bin/pytest tests/test_ohlcv_cache.py -v
```

예상 결과: 10개 모두 PASSED

- [ ] **Step 5: 커밋**

```bash
git add core/data/ohlcv_cache.py tests/test_ohlcv_cache.py
git commit -m "feat: ohlcv_cache 모듈 추가 — DuckDB 캐시 우선 OHLCV 조회"
```

---

### Task 3: `prices_provider.py` 교체

**Files:**
- Modify: `core/data/prices_provider.py`

- [ ] **Step 1: 기존 테스트 통과 상태 확인**

```bash
.venv/bin/pytest tests/test_backtest_api.py -v 2>&1 | tail -15
```

예상 결과: 전체 PASSED (기준선 확보)

- [ ] **Step 2: `prices_provider.py` 전체 교체**

`core/data/prices_provider.py` 내용을 아래로 교체:

```python
"""OHLCV 페치 — DuckDB 캐시 우선, 미스 시 yfinance."""
from datetime import date

import pandas as pd

from core.data.ohlcv_cache import fetch_ohlcv as _fetch_ohlcv


def fetch_ohlcv(
    tickers: list[str], start: date, end: date
) -> tuple[pd.DataFrame, list[str]]:
    """tickers에 대해 OHLCV MultiIndex DataFrame 반환.

    columns: MultiIndex (ticker, field), field ∈ {Open, High, Low, Close, Volume}
    index: DatetimeIndex tz-naive

    Returns:
        (prices, warnings)  prices가 빈 DataFrame이면 유효 종목 없음.
    """
    return _fetch_ohlcv(tickers, start, end)
```

- [ ] **Step 3: 기존 테스트 그대로 통과 확인**

```bash
.venv/bin/pytest tests/test_backtest_api.py -v 2>&1 | tail -15
```

예상 결과: 기존과 동일하게 전체 PASSED  
(`patch("yfinance.download", ...)` 패치가 `ohlcv_cache` 내부까지 적용되므로 동작 동일)

- [ ] **Step 4: 커밋**

```bash
git add core/data/prices_provider.py
git commit -m "feat: prices_provider를 ohlcv_cache 위임으로 교체"
```

---

### Task 4: `index_provider.py` 교체

**Files:**
- Modify: `core/data/index_provider.py`

- [ ] **Step 1: `index_provider.py` 수정**

`core/data/index_provider.py`의 `fetch_market_index` 함수 본문을 아래로 교체 (import 포함, 나머지 함수 `compute_ma`, `is_below_ma`, `resolve_index_symbol`은 그대로 유지):

```python
"""시장 지수 OHLCV 제공자."""
from __future__ import annotations

from datetime import date

import pandas as pd

from core.data.ohlcv_cache import fetch_index as _fetch_index

_INDEX_SYMBOLS = {
    "spy": "SPY",
    "kospi": "^KS11",
}


def fetch_market_index(
    symbol: str,  # "spy" | "kospi"
    start: date,
    end: date,
) -> pd.Series:
    """시장 지수 종가 시계열 반환 (tz-naive)."""
    yf_sym = _INDEX_SYMBOLS.get(symbol.lower(), symbol)
    series = _fetch_index(yf_sym, start, end)
    if series.empty:
        return series
    series.name = symbol  # "spy" / "kospi" 이름 유지
    return series


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def is_below_ma(series: pd.Series, window: int) -> pd.Series:
    """True면 하락장 (series < MA)."""
    return series < compute_ma(series, window)


def resolve_index_symbol(tickers: list[str], hint: str = "auto") -> str:
    """'auto'일 때 종목 리스트에서 한국 종목 비율로 spy/kospi 결정."""
    if hint != "auto":
        return hint
    korean = sum(1 for t in tickers if t.endswith(".KS") or t.endswith(".KQ"))
    return "kospi" if korean >= len(tickers) / 2 else "spy"
```

- [ ] **Step 2: 인덱스 캐시 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_ohlcv_cache.py::test_fetch_index_cache_miss_calls_yfinance tests/test_ohlcv_cache.py::test_fetch_index_cache_hit_skips_yfinance -v
```

예상 결과: 2개 PASSED

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
.venv/bin/pytest tests/ -v 2>&1 | tail -20
```

예상 결과: 전체 PASSED (기존 테스트 포함)

- [ ] **Step 4: 커밋**

```bash
git add core/data/index_provider.py
git commit -m "feat: index_provider를 ohlcv_cache 위임으로 교체 — DuckDB 캐시 완성"
```
