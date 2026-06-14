"""종목별 성과/이평선 테이블용 공통 계산."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import pandas as pd

from core.data.ohlcv_cache import fetch_ohlcv
from core.data.normalization import normalize_finite_numbers


_EMPTY_ROW = {
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
}


def build_ticker_performance(
    tickers: list[str],
    names: dict[str, str] | None = None,
    *,
    cache_only: bool = False,
) -> list[dict[str, Any]]:
    """OHLCV 캐시/수집 데이터를 읽어 Performance View row를 만든다."""
    today = date.today()
    start = today - timedelta(days=430)
    ohlcv, _ = fetch_ohlcv(tickers, start, today, cache_only=cache_only)
    return compute_ticker_performance(tickers, names=names, ohlcv=ohlcv)


def compute_ticker_performance(
    tickers: list[str],
    *,
    names: dict[str, str] | None = None,
    ohlcv: pd.DataFrame,
) -> list[dict[str, Any]]:
    names = names or {}
    return [normalize_finite_numbers(_row_for_ticker(ticker, names.get(ticker), ohlcv)) for ticker in tickers]


def _row_for_ticker(ticker: str, name: str | None, ohlcv: pd.DataFrame) -> dict[str, Any]:
    base = {"ticker": ticker, "name": name or ticker}
    frame = _ticker_frame(ticker, ohlcv)
    if frame is None or frame.empty:
        return {**base, **_EMPTY_ROW}

    frame = frame.dropna(subset=["Close"]).copy()
    if frame.empty:
        return {**base, **_EMPTY_ROW}

    latest = frame.iloc[-1]
    close = float(latest["Close"])
    previous_close = _nth_close(frame, -2)
    ma20 = _rolling_mean(frame["Close"], 20)
    ma50 = _rolling_mean(frame["Close"], 50)
    ma200 = _rolling_mean(frame["Close"], 200)

    return {
        **base,
        "price": close,
        "change_pct": _pct(close, previous_close),
        "volume": _number(latest.get("Volume")),
        "avg_volume20": _mean_tail(frame["Volume"], 20),
        "perf_1w": _period_return(frame, 5),
        "perf_1m": _period_return(frame, 21),
        "perf_6m": _period_return(frame, 126),
        "perf_ytd": _ytd_return(frame),
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "price_vs_ma20": _pct(close, ma20),
        "price_vs_ma50": _pct(close, ma50),
        "price_vs_ma200": _pct(close, ma200),
        "day_low": _number(latest.get("Low")),
        "day_high": _number(latest.get("High")),
        "range_52w_low": _number(frame["Low"].tail(252).min()),
        "range_52w_high": _number(frame["High"].tail(252).max()),
    }


def _ticker_frame(ticker: str, ohlcv: pd.DataFrame) -> pd.DataFrame | None:
    if ohlcv.empty:
        return None
    if isinstance(ohlcv.columns, pd.MultiIndex):
        if ticker not in ohlcv.columns.get_level_values(0):
            return None
        return ohlcv[ticker]
    return ohlcv


def _rolling_mean(series: pd.Series, window: int) -> float | None:
    if len(series.dropna()) < window:
        return None
    return _number(series.rolling(window).mean().iloc[-1])


def _period_return(frame: pd.DataFrame, sessions: int) -> float | None:
    if len(frame) <= sessions:
        return None
    return _pct(float(frame["Close"].iloc[-1]), float(frame["Close"].iloc[-1 - sessions]))


def _ytd_return(frame: pd.DataFrame) -> float | None:
    latest = float(frame["Close"].iloc[-1])
    current_year = frame.index[-1].year
    year_rows = frame[frame.index.year == current_year]
    if year_rows.empty:
        return None
    return _pct(latest, float(year_rows["Close"].iloc[0]))


def _nth_close(frame: pd.DataFrame, index: int) -> float | None:
    if len(frame) < abs(index):
        return None
    return _number(frame["Close"].iloc[index])


def _mean_tail(series: pd.Series, count: int) -> float | None:
    return _number(series.tail(count).mean())


def _pct(current: float | None, base: float | None) -> float | None:
    if current is None or base is None or base == 0:
        return None
    return (current - base) / base * 100


def _number(value: Any) -> float | int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if number.is_integer():
        return int(number)
    return number
