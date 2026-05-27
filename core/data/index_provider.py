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
