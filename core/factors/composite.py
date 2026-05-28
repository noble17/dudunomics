"""팩터 합성 및 종목 선별."""
from __future__ import annotations

import pandas as pd


def compose(factor_values: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series:
    """각 팩터를 rank() 후 가중 합산.

    NaN은 rank에서 제외되고, 결과 composite score에서도 NaN으로 유지.
    """
    if not factor_values:
        return pd.Series(dtype=float)

    all_tickers: set[str] = set()
    for s in factor_values.values():
        all_tickers.update(s.dropna().index)

    if not all_tickers:
        return pd.Series(dtype=float)

    result = pd.Series(0.0, index=list(all_tickers))
    total_weight = 0.0

    for name, series in factor_values.items():
        w = weights.get(name, 1.0)
        if w == 0:
            continue
        ranked = series.dropna().rank(ascending=True)
        result = result.add(ranked * w, fill_value=0.0)
        total_weight += w

    if total_weight > 0:
        result /= total_weight

    return result


def select_top_n(scores: pd.Series, n: int) -> list[str]:
    """점수 기준 상위 n개 ticker 반환."""
    valid = scores.dropna()
    if valid.empty:
        return []
    return list(valid.nlargest(min(n, len(valid))).index)
