"""월별 리밸런싱 날짜 유틸리티."""
from __future__ import annotations

import pandas as pd


def monthly_signal_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """각 월의 마지막 거래일 목록 반환."""
    if len(index) == 0:
        return []
    s = pd.Series(index, index=index)
    return list(s.resample("ME").last().dropna())


def next_trading_day(ts: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp | None:
    """ts 이후 첫 거래일 반환. 없으면 None."""
    future = index[index > ts]
    return future[0] if len(future) > 0 else None
