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
