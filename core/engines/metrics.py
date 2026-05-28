"""포트폴리오 성과 지표 계산."""
import numpy as np
import pandas as pd


def compute_metrics(equity: pd.Series) -> dict:
    """equity curve에서 CAGR/MDD/Sharpe/total_return/calmar 계산.

    Returns:
        dict: cagr, mdd, sharpe, total_return, calmar (모두 % 단위, sharpe/calmar 제외)
    """
    if equity.empty or len(equity) < 2:
        return {"cagr": 0.0, "mdd": 0.0, "sharpe": 0.0, "total_return": 0.0, "calmar": 0.0}

    rets = equity.pct_change().dropna()
    total_return = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)

    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1e-6)
    cagr = float(((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) * 100)

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    mdd = float(drawdown.min() * 100)

    sharpe = 0.0
    if len(rets) > 1 and rets.std() > 0:
        sharpe = float(rets.mean() / rets.std() * np.sqrt(252))

    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0

    return {
        "cagr": round(cagr, 4),
        "mdd": round(mdd, 4),
        "sharpe": round(sharpe, 4),
        "total_return": round(total_return, 4),
        "calmar": round(calmar, 4),
    }


def per_ticker_contribution(
    prices: pd.DataFrame,
    tickers: list[str],
    initial_weights: pd.Series,
    invested: float,
) -> dict[str, float]:
    """종목별 절대 수익 기여도 (원).

    각 종목: 초기 투자금 × (최종 Close / 초기 Close - 1)
    """
    result: dict[str, float] = {}
    for t in tickers:
        if t not in prices.columns.get_level_values(0):
            result[t] = 0.0
            continue
        sub = prices[t].dropna(how="all")
        close_col = "Close" if "Close" in sub.columns else sub.columns[0]
        closes = sub[close_col].dropna()
        if closes.empty or closes.iloc[0] == 0:
            result[t] = 0.0
            continue
        alloc = invested * float(initial_weights.get(t, 0.0))
        result[t] = round(alloc * (closes.iloc[-1] / closes.iloc[0] - 1), 0)
    return result
