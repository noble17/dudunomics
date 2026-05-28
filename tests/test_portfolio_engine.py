"""1.V.1 — Equal Weight 포트폴리오 엔진 단위 테스트."""
import numpy as np
import pandas as pd
import pytest

from core.engines.metrics import compute_metrics, per_ticker_contribution
from core.engines.portfolio_engine import BacktestContext, run_equal_weight_buy_hold


def _make_prices(tickers: list[str], days: int = 30, start_price: float = 10_000.0) -> pd.DataFrame:
    """테스트용 Close 가격만 있는 MultiIndex DataFrame 생성."""
    dates = pd.date_range("2023-01-01", periods=days, freq="B")
    arrays = []
    for t in tickers:
        close = pd.Series(start_price * np.cumprod(1 + np.random.normal(0, 0.01, days)), index=dates)
        sub = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1_000_000}, index=dates)
        sub.columns = pd.MultiIndex.from_tuples([(t, c) for c in sub.columns])
        arrays.append(sub)
    return pd.concat(arrays, axis=1)


class TestComputeMetrics:
    def test_flat_equity(self):
        eq = pd.Series([10_000_000.0] * 30, index=pd.date_range("2023-01-01", periods=30, freq="B"))
        m = compute_metrics(eq)
        assert m["total_return"] == pytest.approx(0.0, abs=0.01)
        assert m["mdd"] == pytest.approx(0.0, abs=0.01)

    def test_growing_equity_positive_return(self):
        eq = pd.Series(
            [10_000_000.0 * (1.001 ** i) for i in range(252)],
            index=pd.date_range("2023-01-01", periods=252, freq="B"),
        )
        m = compute_metrics(eq)
        assert m["total_return"] > 0
        assert m["cagr"] > 0
        assert m["sharpe"] > 0
        assert m["mdd"] == pytest.approx(0.0, abs=0.1)

    def test_empty_equity(self):
        m = compute_metrics(pd.Series(dtype=float))
        assert m["total_return"] == 0.0


class TestRunEqualWeightBuyHold:
    def test_single_ticker_return_matches_price_change(self):
        """단일 종목: 총 수익률 = (마지막 Close / 첫 Close - 1)."""
        np.random.seed(42)
        prices = _make_prices(["AAPL"], days=252)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)
        result = run_equal_weight_buy_hold(ctx)

        close = prices["AAPL"]["Close"]
        expected_return = (close.iloc[-1] / close.iloc[0] - 1) * 100

        # 수수료 0.2% 차감 후 근사값 일치 (1% 오차 허용)
        assert abs(result.metrics["total_return"] - expected_return) < 1.0

    def test_equal_weight_initial_weights(self):
        """3 종목: 첫날 비중이 각각 1/3."""
        np.random.seed(1)
        prices = _make_prices(["A", "B", "C"], days=30)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0)
        result = run_equal_weight_buy_hold(ctx)

        first_weights = result.weights_history.iloc[0]
        for t in ["A", "B", "C"]:
            assert first_weights[t] == pytest.approx(1 / 3, abs=0.05)

    def test_equity_curve_starts_near_cash(self):
        """자산 곡선 첫날이 투자금(수수료 차감 후)에 근사."""
        np.random.seed(2)
        prices = _make_prices(["X", "Y"], days=10)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)
        result = run_equal_weight_buy_hold(ctx)
        assert result.equity_curve.iloc[0] == pytest.approx(10_000_000 * 0.998, rel=0.01)

    def test_empty_prices_returns_empty_result(self):
        ctx = BacktestContext(prices=pd.DataFrame(), cash=10_000_000.0)
        result = run_equal_weight_buy_hold(ctx)
        assert result.equity_curve.empty
        assert "보유 종목 없음" in result.warnings

    def test_warnings_passed_through(self):
        np.random.seed(3)
        prices = _make_prices(["Z"], days=10)
        ctx = BacktestContext(prices=prices)
        warns = ["테스트 경고"]
        result = run_equal_weight_buy_hold(ctx, warns=warns)
        assert "테스트 경고" in result.warnings
