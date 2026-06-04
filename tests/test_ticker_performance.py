from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def _ohlcv(ticker: str, days: int = 260) -> pd.DataFrame:
    start = date(2025, 1, 1)
    idx = pd.to_datetime([start + timedelta(days=i) for i in range(days)])
    close = [100.0 + i for i in range(days)]
    frame = pd.DataFrame({
        "Open": close,
        "High": [v + 1 for v in close],
        "Low": [v - 1 for v in close],
        "Close": close,
        "Volume": [1_000 + i * 10 for i in range(days)],
    }, index=idx)
    return pd.concat({ticker: frame}, axis=1)


def test_compute_ticker_performance_includes_returns_and_ma_values():
    from core.analytics.ticker_performance import compute_ticker_performance

    rows = compute_ticker_performance(
        ["AAPL"],
        names={"AAPL": "Apple"},
        ohlcv=_ohlcv("AAPL"),
    )

    row = rows[0]
    assert row["ticker"] == "AAPL"
    assert row["name"] == "Apple"
    assert row["price"] == 359.0
    assert row["volume"] == 3590
    assert row["avg_volume20"] == 3495.0
    assert row["perf_1w"] == 500 / 354
    assert row["perf_ytd"] == 25900 / 100
    assert row["ma20"] == 349.5
    assert row["ma50"] == 334.5
    assert row["ma200"] == 259.5
    assert row["price_vs_ma20"] == (359.0 - 349.5) / 349.5 * 100
    assert row["day_low"] == 358.0
    assert row["day_high"] == 360.0
    assert row["range_52w_low"] == 107.0
    assert row["range_52w_high"] == 360.0


def test_compute_ticker_performance_returns_nulls_when_ohlcv_missing():
    from core.analytics.ticker_performance import compute_ticker_performance

    rows = compute_ticker_performance(["MISS"], names={"MISS": "Missing"}, ohlcv=pd.DataFrame())

    assert rows == [{
        "ticker": "MISS",
        "name": "Missing",
        "price": None,
        "change_pct": None,
        "volume": None,
        "avg_volume20": None,
        "perf_1w": None,
        "perf_1m": None,
        "perf_6m": None,
        "perf_ytd": None,
        "ma20": None,
        "ma50": None,
        "ma200": None,
        "price_vs_ma20": None,
        "price_vs_ma50": None,
        "price_vs_ma200": None,
        "day_low": None,
        "day_high": None,
        "range_52w_low": None,
        "range_52w_high": None,
    }]
