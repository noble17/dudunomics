"""시장 지수 OHLCV 제공자."""
from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

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
    df = yf.download(yf_sym, start=str(start), end=str(end), progress=False, auto_adjust=True)
    if df.empty:
        return pd.Series(dtype=float)

    # MultiIndex 컬럼 처리 (yfinance >= 0.2.x)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close = df["Close"].squeeze()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    # tz-naive 정규화
    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    return close.rename(symbol)


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
