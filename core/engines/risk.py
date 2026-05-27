"""마켓 필터 + 역변동성 비중 계산."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from api.models import RiskOptions


def inverse_volatility_weights(
    prices: pd.DataFrame,
    tickers: list[str],
    as_of: pd.Timestamp,
    lookback: int,
) -> pd.Series:
    """최근 lookback일 종가 표준편차 역수로 비중 정규화.

    반환: index=ticker, value=weight (합=1)
    """
    # Close 컬럼 추출
    try:
        close = prices.xs("Close", axis=1, level=1)
    except KeyError:
        close = prices.xs("close", axis=1, level=1)

    window = close.loc[:as_of, tickers].tail(lookback)
    rets = window.pct_change().dropna(how="all")

    if rets.empty or len(rets) < 2:
        # 데이터 부족: 동일 비중 fallback
        n = len(tickers)
        return pd.Series(1.0 / n, index=tickers)

    vols = rets.std()
    inv = 1.0 / vols.replace(0, np.nan)
    total = inv.sum()
    if total == 0 or np.isnan(total):
        n = len(tickers)
        return pd.Series(1.0 / n, index=tickers)
    return (inv / total).fillna(0.0)


def apply_market_filter(
    weights: pd.Series,
    as_of: pd.Timestamp,
    market_index: pd.Series,
    opts: "RiskOptions",
) -> pd.Series:
    """하락장(index < MA)이면 주식 비중을 (1-reduction)배 축소.

    반환: weights (합 ≤ 1, 나머지는 현금)
    """
    window = market_index.loc[:as_of]
    if len(window) < opts.market_filter_ma_days:
        return weights  # 데이터 부족 → 필터 미적용

    ma = window.rolling(opts.market_filter_ma_days).mean().iloc[-1]
    current = window.iloc[-1]
    if pd.isna(ma) or pd.isna(current):
        return weights

    if current < ma:
        return weights * (1.0 - opts.market_filter_reduction)
    return weights


def compute_weights(
    tickers: list[str],
    prices: pd.DataFrame,
    as_of: pd.Timestamp,
    opts: "RiskOptions",
    market_index: pd.Series | None,
) -> pd.Series:
    """비중 계산: (1) equal 또는 inverse_vol, (2) market_filter 적용.

    반환: index=ticker, value=weight (현금 비중 = 1 - weights.sum())
    """
    if opts.weighting == "inverse_vol":
        base = inverse_volatility_weights(prices, tickers, as_of, opts.vol_lookback_days)
    else:
        n = len(tickers)
        base = pd.Series(1.0 / n, index=tickers)

    if opts.market_filter and market_index is not None:
        base = apply_market_filter(base, as_of, market_index, opts)

    return base
