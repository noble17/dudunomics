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
