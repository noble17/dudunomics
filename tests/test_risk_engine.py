"""3단계 risk 엔진 단위 테스트 + 회귀 테스트."""
import numpy as np
import pandas as pd
import pytest

from core.engines.risk import apply_market_filter, compute_weights, inverse_volatility_weights


def _make_prices(tickers: list[str], days: int = 60, start_price: float = 10_000.0) -> pd.DataFrame:
    """테스트용 MultiIndex(ticker, field) DataFrame 생성."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=days, freq="B")
    parts = []
    for t in tickers:
        close = pd.Series(start_price * np.cumprod(1 + np.random.normal(0, 0.01, days)), index=dates)
        sub = pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1_000_000},
            index=dates,
        )
        sub.columns = pd.MultiIndex.from_tuples([(t, c) for c in sub.columns])
        parts.append(sub)
    return pd.concat(parts, axis=1)


def test_inverse_vol_weights_sum_to_one():
    """inverse_volatility_weights: 3개 종목 비중 합 = 1."""
    prices = _make_prices(["A", "B", "C"], days=60)
    as_of = prices.index[-1]
    weights = inverse_volatility_weights(prices, ["A", "B", "C"], as_of, lookback=20)
    assert abs(weights.sum() - 1.0) < 1e-9
    assert (weights >= 0).all()


def test_inverse_vol_weights_low_vol_gets_higher_weight():
    """inverse_volatility_weights: 저변동 종목이 고변동 종목보다 높은 비중."""
    np.random.seed(0)
    dates = pd.date_range("2023-01-01", periods=60, freq="B")

    high_vol = pd.Series(100.0 * np.cumprod(1 + np.random.normal(0, 0.05, 60)), index=dates)
    low_vol = pd.Series(100.0 * np.cumprod(1 + np.random.normal(0, 0.005, 60)), index=dates)

    def _col(t, s):
        sub = pd.DataFrame({"Close": s}, index=dates)
        sub.columns = pd.MultiIndex.from_tuples([(t, c) for c in sub.columns])
        return sub

    prices = pd.concat([_col("HIGH", high_vol), _col("LOW", low_vol)], axis=1)
    as_of = dates[-1]
    weights = inverse_volatility_weights(prices, ["HIGH", "LOW"], as_of, lookback=20)
    assert weights["LOW"] > weights["HIGH"]


def test_apply_market_filter_reduces_weights_in_bear_market():
    """apply_market_filter: 하락장(현재 < 200일 MA)에서 비중을 50% 축소."""
    from api.models import RiskOptions

    dates = pd.date_range("2019-01-01", periods=300, freq="B")
    index_vals = pd.Series(
        [100.0] * 150 + [70.0] * 150,
        index=dates,
    )
    opts = RiskOptions(market_filter=True, market_filter_ma_days=200, market_filter_reduction=0.5)
    weights_in = pd.Series({"A": 0.5, "B": 0.5})

    bear_ts = dates[-1]
    weights_out = apply_market_filter(weights_in, bear_ts, index_vals, opts)
    assert weights_out.sum() < weights_in.sum()
    assert abs(weights_out.sum() - 0.5) < 0.01


def test_apply_market_filter_keeps_weights_in_bull_market():
    """apply_market_filter: 상승장(현재 > 200일 MA)에서 비중 유지."""
    from api.models import RiskOptions

    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    index_vals = pd.Series(
        [70.0] * 150 + [100.0] * 150,
        index=dates,
    )
    opts = RiskOptions(market_filter=True, market_filter_ma_days=200, market_filter_reduction=0.5)
    weights_in = pd.Series({"A": 0.5, "B": 0.5})

    bull_ts = dates[-1]
    weights_out = apply_market_filter(weights_in, bull_ts, index_vals, opts)
    assert abs(weights_out.sum() - weights_in.sum()) < 0.01


def test_compute_weights_equal_mode():
    """compute_weights: equal 모드에서 동일 비중(1/N) 반환."""
    from api.models import RiskOptions

    prices = _make_prices(["X", "Y", "Z"], days=30)
    opts = RiskOptions(weighting="equal", market_filter=False)
    as_of = prices.index[-1]
    w = compute_weights(["X", "Y", "Z"], prices, as_of, opts, market_index=None)
    assert abs(w.sum() - 1.0) < 1e-9
    for t in ["X", "Y", "Z"]:
        assert abs(w[t] - 1.0 / 3) < 1e-9


def test_equal_weight_no_risk_options_regression():
    """risk_options=None일 때 BacktestContext 기존 동작 불변 (회귀)."""
    from core.engines.portfolio_engine import BacktestContext, run_equal_weight_buy_hold

    prices = _make_prices(["AAPL", "MSFT"], days=60, start_price=100.0)
    ctx_base = BacktestContext(prices=prices, risk_options=None)
    ctx_risk = BacktestContext(prices=prices, risk_options=None)

    res_base = run_equal_weight_buy_hold(ctx_base)
    res_risk = run_equal_weight_buy_hold(ctx_risk)

    assert np.allclose(res_base.equity_curve.values, res_risk.equity_curve.values)
