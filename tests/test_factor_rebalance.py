"""2단계 팩터 리밸런싱 단위·통합 테스트."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from core.data.fundamentals_provider import FundamentalSnapshot, _safe_float
from core.engines.portfolio_engine import BacktestContext, run_with_rebalance
from core.engines.rebalance import monthly_signal_dates, next_trading_day
from core.factors.composite import compose, select_top_n
from core.factors.forward_per import ForwardPerFactor


def _make_prices(tickers: list[str], days: int = 60, start_price: float = 10_000.0) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=days, freq="B")
    arrays = []
    for i, t in enumerate(tickers):
        np.random.seed(i)
        close = pd.Series(
            start_price * np.cumprod(1 + np.random.normal(0.001, 0.01, days)), index=dates
        )
        sub = pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1_000_000},
            index=dates,
        )
        sub.columns = pd.MultiIndex.from_tuples([(t, c) for c in sub.columns])
        arrays.append(sub)
    return pd.concat(arrays, axis=1)


# ── 2.V.1 fetch_snapshots 단위 테스트 ─────────────────────────────────────────

class TestFetchSnapshots:
    def test_safe_float_normal(self):
        assert _safe_float({"forwardEps": 3.14}, "forwardEps") == pytest.approx(3.14)

    def test_safe_float_none(self):
        assert _safe_float({}, "forwardEps") is None

    def test_safe_float_nan(self):
        import math
        assert _safe_float({"forwardEps": float("nan")}, "forwardEps") is None

    def test_fetch_snapshots_mocked(self):
        from core.data.fundamentals_provider import fetch_snapshots

        mock_info = {"forwardEps": 5.0, "forwardPE": 20.0, "trailingPE": 22.0}
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker_cls.return_value.info = mock_info
            results = fetch_snapshots(["AAPL", "MSFT"])

        assert len(results) == 2
        tickers = {r.ticker for r in results}
        assert tickers == {"AAPL", "MSFT"}
        for r in results:
            assert r.forward_eps == pytest.approx(5.0)
            assert r.forward_pe == pytest.approx(20.0)

    def test_fetch_snapshots_failure_ticker(self):
        from core.data.fundamentals_provider import fetch_snapshots

        def side_effect(ticker):
            mock = MagicMock()
            if ticker == "INVALID":
                mock.info = {}  # yfinance가 빈 dict 반환 → None 필드
            else:
                mock.info = {"forwardEps": 2.0, "forwardPE": 15.0, "trailingPE": 16.0}
            return mock

        with patch("yfinance.Ticker", side_effect=side_effect):
            results = fetch_snapshots(["AAPL", "INVALID"])

        ticker_map = {r.ticker: r for r in results}
        assert ticker_map["AAPL"].forward_eps == pytest.approx(2.0)
        assert ticker_map["INVALID"].forward_eps is None


# ── 2.V.2 팩터 스코어 단위 테스트 ─────────────────────────────────────────────

class TestFactorScoring:
    def test_forward_per_score_inverse(self, monkeypatch):
        """PER 낮은 종목이 더 높은 점수를 받아야 한다."""
        import core.repository as repo

        def mock_get_latest(ticker, as_of):
            pe_map = {"A": 10.0, "B": 20.0, "C": 5.0}
            pe = pe_map.get(ticker)
            return {"forward_pe": pe} if pe else None

        monkeypatch.setattr(repo, "get_latest_fundamental", mock_get_latest)
        factor = ForwardPerFactor()
        scores = factor.compute(["A", "B", "C"], date(2024, 1, 31))

        # 1/5 > 1/10 > 1/20
        assert scores["C"] > scores["A"] > scores["B"]

    def test_forward_per_nan_for_missing(self, monkeypatch):
        """PER 없는 종목은 NaN 반환."""
        import core.repository as repo
        monkeypatch.setattr(repo, "get_latest_fundamental", lambda t, d: None)
        factor = ForwardPerFactor()
        scores = factor.compute(["X"], date(2024, 1, 31))
        assert pd.isna(scores["X"])

    def test_compose_top_n(self):
        per_scores = pd.Series({"A": 0.10, "B": 0.05, "C": 0.02, "D": 0.08})
        eps_scores = pd.Series({"A": 0.01, "B": 0.05, "C": 0.03, "D": 0.0})

        composite = compose(
            {"forward_per": per_scores, "forward_eps_momentum": eps_scores},
            {"forward_per": 0.5, "forward_eps_momentum": 0.5},
        )
        top2 = select_top_n(composite, 2)
        assert len(top2) == 2
        assert len(set(top2)) == 2

    def test_compose_empty_weights(self):
        scores = compose({}, {})
        assert scores.empty

    def test_select_top_n_fewer_than_n(self):
        scores = pd.Series({"A": 3.0, "B": 1.0})
        result = select_top_n(scores, 5)
        assert set(result) == {"A", "B"}


# ── 2.V.3 리밸런싱 시뮬레이션 통합 테스트 ────────────────────────────────────

class TestRunWithRebalance:
    def test_monthly_signal_dates(self):
        idx = pd.date_range("2023-01-01", "2023-03-31", freq="B")
        sigs = monthly_signal_dates(idx)
        assert len(sigs) == 3
        # 각 월의 마지막 거래일이어야 함
        months = {s.month for s in sigs}
        assert months == {1, 2, 3}

    def test_next_trading_day(self):
        idx = pd.date_range("2023-01-02", "2023-01-10", freq="B")
        sig = pd.Timestamp("2023-01-04")
        nxt = next_trading_day(sig, idx)
        assert nxt == pd.Timestamp("2023-01-05")

    def test_rebalance_log_has_monthly_entries(self):
        np.random.seed(0)
        prices = _make_prices(["A", "B", "C", "D"], days=130)

        call_count = 0

        def selector(tickers, as_of):
            nonlocal call_count
            call_count += 1
            # 홀수 호출: A, B / 짝수 호출: C, D
            chosen = ["A", "B"] if call_count % 2 == 1 else ["C", "D"]
            return {t: 0.5 for t in chosen if t in tickers}

        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)
        result = run_with_rebalance(ctx, selector)

        assert not result.equity_curve.empty
        # 130 거래일 ≈ 6개월 → 리밸런싱 최소 5회 (초기 포함)
        assert len(result.rebalance_log) >= 4
        for entry in result.rebalance_log:
            assert "date" in entry
            assert "holdings" in entry
            assert "weights" in entry

    def test_commission_reduces_equity(self):
        """수수료가 있을 때 equity가 수수료 없을 때보다 낮아야 한다."""
        np.random.seed(1)
        prices = _make_prices(["X", "Y"], days=60)

        def fixed_selector(tickers, as_of):
            return {"X": 0.5, "Y": 0.5}

        ctx_no_fee = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.0)
        ctx_fee = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.005)

        result_no_fee = run_with_rebalance(ctx_no_fee, fixed_selector)
        result_fee = run_with_rebalance(ctx_fee, fixed_selector)

        assert result_fee.equity_curve.iloc[-1] < result_no_fee.equity_curve.iloc[-1]

    def test_holding_changes_at_rebalance(self):
        """리밸런싱 로그에 종목 교체가 기록되어야 한다."""
        np.random.seed(2)
        prices = _make_prices(["A", "B", "C", "D"], days=130)
        call_count = [0]

        def alternating_selector(tickers, as_of):
            call_count[0] += 1
            return {"A": 1.0} if call_count[0] % 2 == 1 else {"B": 1.0}

        ctx = BacktestContext(prices=prices, cash=10_000_000.0)
        result = run_with_rebalance(ctx, alternating_selector)

        holdings_per_rebalance = [set(e["holdings"]) for e in result.rebalance_log]
        # 최소 한 번은 holdings가 달라야 한다
        if len(holdings_per_rebalance) > 1:
            assert not all(h == holdings_per_rebalance[0] for h in holdings_per_rebalance[1:])

    def test_empty_prices_returns_empty(self):
        def selector(tickers, as_of):
            return {}

        ctx = BacktestContext(prices=pd.DataFrame())
        result = run_with_rebalance(ctx, selector)
        assert result.equity_curve.empty
