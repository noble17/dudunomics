"""OHLCV 페치 — DuckDB 캐시 우선, 미스 시 yfinance."""
from datetime import date

import pandas as pd

from core.data.ohlcv_cache import fetch_ohlcv as _fetch_ohlcv


def fetch_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_only: bool = False,
    force: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """tickers에 대해 OHLCV MultiIndex DataFrame 반환.

    cache_only=True: 캐시만 조회. force=True: 강제 재페치.
    """
    return _fetch_ohlcv(tickers, start, end, cache_only=cache_only, force=force)
