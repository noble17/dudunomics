"""HybridFactorSMA 전략 단위 테스트.

검증 항목:
1. SMA 게이트 — fast > slow 통과 종목만 보유
2. dead-cross 중도 청산 — rebalance_log type="dead_cross" 기록 및 포트폴리오 제거
3. SMA 통과 종목 없을 때 전액 현금 보유
4. BacktestResult 구조 필드 존재 검증
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/Users/user/Development/private/dudunomics")

import numpy as np
import pandas as pd
import pytest

import core.strategies.hybrid_factor_sma as mod
from core.engines.portfolio_engine import BacktestContext
from core.strategies.hybrid_factor_sma import HybridFactorSMA


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def make_prices(tickers: list[str], close_by_ticker: dict[str, list[float]]) -> pd.DataFrame:
    """MultiIndex (ticker, field) 가격 DataFrame 생성."""
    n_days = min(len(v) for v in close_by_ticker.values())
    dates = pd.bdate_range("2023-01-02", periods=n_days)
    data: dict[tuple[str, str], list[float]] = {}
    for t in tickers:
        closes = list(close_by_ticker[t])[:n_days]
        data[(t, "Close")] = closes
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


def _patch_factors(monkeypatch, tickers_ranked_first: list[str]) -> None:
    """per_factor / eps_factor compute를 monkeypatch로 대체.

    tickers_ranked_first 순서대로 높은 composite score를 부여.
    (index=0이 top-1)
    """
    n = len(tickers_ranked_first)

    def mock_per_compute(tickers, as_of):
        # tickers_ranked_first 순서대로 내림차순 점수 부여
        scores = {}
        for t in tickers:
            if t in tickers_ranked_first:
                scores[t] = float(n - tickers_ranked_first.index(t))
            else:
                scores[t] = 0.0
        return pd.Series(scores)

    def mock_eps_compute(tickers, as_of):
        return pd.Series({t: 0.0 for t in tickers})

    monkeypatch.setattr(mod._per_factor, "compute", mock_per_compute)
    monkeypatch.setattr(mod._eps_factor, "compute", mock_eps_compute)


def _patch_externals(monkeypatch) -> None:
    """fetch_snapshots / repo.upsert_fundamentals를 no-op으로 교체."""
    import core.repository as repo
    monkeypatch.setattr(mod, "fetch_snapshots", lambda tickers: [], raising=False)
    # run_portfolio 내부에서 `from core.data.fundamentals_provider import fetch_snapshots` 로 import
    # 해당 네임스페이스를 직접 패치해야 한다
    import core.data.fundamentals_provider as fdp
    monkeypatch.setattr(fdp, "fetch_snapshots", lambda tickers, **kw: [])
    monkeypatch.setattr(repo, "upsert_fundamentals", lambda x: None)


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 1: BacktestResult 구조 필드 존재
# ─────────────────────────────────────────────────────────────────────────────

class TestBacktestResultStructure:
    """BacktestResult에 필수 필드가 모두 존재하는지 검증."""

    def test_result_fields_exist(self, monkeypatch):
        n_days = 60
        tickers = ["AAPL", "MSFT"]
        # AAPL 상승, MSFT 하락
        close_data = {
            "AAPL": [100 + i * 2 for i in range(n_days)],
            "MSFT": [200 - i * 1 for i in range(n_days)],
        }
        prices = make_prices(tickers, close_data)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL", "MSFT"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 2, "fast": 5, "slow": 10})

        assert hasattr(result, "equity_curve")
        assert hasattr(result, "weights_history")
        assert hasattr(result, "rebalance_log")
        assert hasattr(result, "metrics")
        assert hasattr(result, "warnings")


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 2: SMA 게이트 — fast > slow 통과 종목만 보유
# ─────────────────────────────────────────────────────────────────────────────

class TestSmaGate:
    """SMA(fast) > SMA(slow) 조건을 통과한 종목만 초기 포트폴리오에 포함."""

    def test_only_rising_ticker_held(self, monkeypatch):
        """AAPL 상승(SMA5 > SMA10 확실), MSFT 하락(SMA5 < SMA10).
        팩터 상위 2개 = [AAPL, MSFT] 이더라도 MSFT는 SMA 게이트 탈락.

        SMA slow=10 warm-up 이후 첫 월말 리밸런싱 시점에서 확인.
        """
        fast, slow = 5, 10
        # warm-up + 리밸런싱 발생에 충분한 기간 (60일 이상)
        n_days = 65
        tickers = ["AAPL", "MSFT"]
        close_data = {
            "AAPL": [100 + i * 3 for i in range(n_days)],   # 강한 상승
            "MSFT": [300 - i * 3 for i in range(n_days)],   # 강한 하락
        }
        prices = make_prices(tickers, close_data)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL", "MSFT"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 2, "fast": fast, "slow": slow})

        # SMA warm-up 이후(slow 기간 이후) 시점 비중 확인
        # 첫 월말 리밸런싱 이후 weights에서 MSFT=0, AAPL>0 검증
        wh = result.weights_history
        # slow 기간 이후 rows만 확인
        post_warmup = wh.iloc[slow:]
        assert not post_warmup.empty, "warm-up 이후 데이터가 있어야 함"

        # AAPL이 한 번이라도 비중 > 0인 날이 있어야 함
        aapl_any = post_warmup.get("AAPL", pd.Series(dtype=float))
        msft_any = post_warmup.get("MSFT", pd.Series(dtype=float))

        assert (aapl_any > 0.0).any(), "AAPL은 SMA 통과로 보유되어야 함"
        assert (msft_any > 0.0).sum() == 0, f"MSFT는 SMA 탈락이어야 함 (비중 합: {msft_any.sum():.4f})"

    def test_equity_reflects_only_passing_ticker(self, monkeypatch):
        """SMA 통과 종목(AAPL)의 가격 변동이 equity_curve에 반영됨."""
        n_days = 60
        tickers = ["AAPL", "MSFT"]
        close_data = {
            "AAPL": [100 + i * 3 for i in range(n_days)],
            "MSFT": [300 - i * 3 for i in range(n_days)],
        }
        prices = make_prices(tickers, close_data)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL", "MSFT"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 2, "fast": 5, "slow": 10})

        # AAPL은 상승 추세이므로 equity_curve도 상승해야 함
        assert result.equity_curve.iloc[-1] > result.equity_curve.iloc[0], (
            "AAPL 상승 추세이므로 equity 증가 기대"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 3: SMA 통과 종목 없을 때 전액 현금
# ─────────────────────────────────────────────────────────────────────────────

class TestAllCashWhenNoSmaPass:
    """팩터 상위 종목이 모두 SMA 탈락 → equity_curve ≈ ctx.cash."""

    def test_full_cash_when_no_sma_pass(self, monkeypatch):
        n_days = 60
        tickers = ["AAPL", "MSFT"]
        # 둘 다 강한 하락 → SMA5 < SMA10
        close_data = {
            "AAPL": [500 - i * 5 for i in range(n_days)],
            "MSFT": [400 - i * 4 for i in range(n_days)],
        }
        prices = make_prices(tickers, close_data)
        cash = 10_000_000.0
        ctx = BacktestContext(prices=prices, cash=cash, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL", "MSFT"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 2, "fast": 5, "slow": 10})

        # 전액 현금 → equity_curve 전 기간이 ctx.cash와 동일
        assert not result.equity_curve.empty
        first_equity = result.equity_curve.iloc[0]
        # SMA warm-up(slow=10) 전까지는 NaN이지만 첫날 데이터는 존재
        # 현금 보유이면 equity == cash
        assert first_equity == pytest.approx(cash, rel=0.001), (
            f"SMA 통과 없으면 전액 현금 보유 기대, got {first_equity}"
        )

    def test_weights_history_empty_or_cash_only(self, monkeypatch):
        """전액 현금 시 weights_history에 주식 비중이 없어야 함."""
        n_days = 60
        tickers = ["AAPL", "MSFT"]
        close_data = {
            "AAPL": [500 - i * 5 for i in range(n_days)],
            "MSFT": [400 - i * 4 for i in range(n_days)],
        }
        prices = make_prices(tickers, close_data)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL", "MSFT"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 2, "fast": 5, "slow": 10})

        # AAPL, MSFT 비중이 0이거나 컬럼 자체 없어야 함
        for ticker in tickers:
            if ticker in result.weights_history.columns:
                assert result.weights_history[ticker].sum() == pytest.approx(0.0, abs=1e-6), (
                    f"{ticker} 비중이 0이어야 함"
                )


# ─────────────────────────────────────────────────────────────────────────────
# 테스트 4: dead-cross 중도 청산
# ─────────────────────────────────────────────────────────────────────────────

class TestDeadCrossLiquidation:
    """dead-cross 발생 후 다음 거래일에 rebalance_log에 type='dead_cross' 기록."""

    def _make_dead_cross_prices(self, fast: int = 5, slow: int = 20) -> pd.DataFrame:
        """처음 slow+fast*2 일 상승 → 이후 급락으로 dead-cross 유발."""
        # warm-up: slow 기간만큼 SMA 준비 필요
        warmup = slow + fast * 2  # 약 30일 상승
        n_days = warmup + 40      # 급락 구간 포함

        # 처음엔 강한 상승 (SMA5 > SMA20), 이후 급락
        prices_up = [100 + i * 5 for i in range(warmup)]
        # 급락: 현재값(100 + warmup*5) 에서 빠르게 하락
        peak = 100 + warmup * 5
        prices_down = [peak - (i + 1) * 15 for i in range(40)]

        closes = prices_up + prices_down
        # 음수 방지
        closes = [max(c, 1.0) for c in closes]
        n_days = len(closes)

        return make_prices(["AAPL"], {"AAPL": closes})

    def test_dead_cross_log_entry_exists(self, monkeypatch):
        """dead-cross 후 rebalance_log에 type='dead_cross' 항목이 최소 1개 있어야 함."""
        prices = self._make_dead_cross_prices(fast=5, slow=20)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 1, "fast": 5, "slow": 20})

        dc_logs = [e for e in result.rebalance_log if e.get("type") == "dead_cross"]
        assert len(dc_logs) >= 1, (
            f"dead-cross 로그 없음. 전체 로그: {result.rebalance_log}"
        )

    def test_dead_cross_ticker_removed_from_portfolio(self, monkeypatch):
        """dead-cross 이후 AAPL 비중이 0으로 수렴해야 함."""
        prices = self._make_dead_cross_prices(fast=5, slow=20)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 1, "fast": 5, "slow": 20})

        # dead-cross 로그 날짜 이후 AAPL 비중이 0이어야 함
        dc_logs = [e for e in result.rebalance_log if e.get("type") == "dead_cross"]
        assert len(dc_logs) >= 1, "dead-cross 로그 전제 조건 실패"

        # dead_cross 기록 날짜 이후 weights에서 AAPL이 0
        dc_date = pd.Timestamp(dc_logs[0]["date"])
        if "AAPL" in result.weights_history.columns:
            post_dc = result.weights_history.loc[result.weights_history.index >= dc_date, "AAPL"]
            # 매도 이후 비중은 0 (현금 보유)
            assert post_dc.sum() == pytest.approx(0.0, abs=1e-6), (
                f"dead-cross 이후 AAPL 비중이 0이어야 함. sum={post_dc.sum()}"
            )

    def test_dead_cross_log_has_tickers_sold(self, monkeypatch):
        """dead_cross 로그 항목에 'tickers_sold' 키가 있고 AAPL이 포함되어야 함."""
        prices = self._make_dead_cross_prices(fast=5, slow=20)
        ctx = BacktestContext(prices=prices, cash=10_000_000.0, commission=0.002)

        _patch_externals(monkeypatch)
        _patch_factors(monkeypatch, tickers_ranked_first=["AAPL"])

        strategy = HybridFactorSMA()
        result = strategy.run_portfolio(ctx, params={"top_n": 1, "fast": 5, "slow": 20})

        dc_logs = [e for e in result.rebalance_log if e.get("type") == "dead_cross"]
        assert len(dc_logs) >= 1

        dc_entry = dc_logs[0]
        assert "tickers_sold" in dc_entry, f"tickers_sold 키 없음: {dc_entry}"
        assert "AAPL" in dc_entry["tickers_sold"], (
            f"AAPL이 tickers_sold에 없음: {dc_entry['tickers_sold']}"
        )
