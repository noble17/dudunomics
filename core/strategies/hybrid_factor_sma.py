"""하이브리드 전략: 복합 팩터 상위 N + SMA 골든/데드 크로스 필터."""
from __future__ import annotations

from typing import ClassVar

import pandas as pd

from core.engines.portfolio_engine import (
    BacktestContext,
    BacktestResult,
    _get_close,
    _safe_price,
)
from core.engines.metrics import compute_metrics, per_ticker_contribution
from core.factors.composite import compose, select_top_n
from core.factors.forward_eps_momentum import ForwardEpsMomentumFactor
from core.factors.forward_per import ForwardPerFactor
from core.strategies.base import Strategy, register

_LOOK_AHEAD_WARNING = (
    "⚠ Look-ahead bias: yfinance forward EPS/PER은 현재 시점 스냅샷입니다. "
    "과거 시점의 실제 forward 데이터를 쓰지 않아 백테스트 수익률이 실제와 다를 수 있습니다."
)
_EPS_MOMENTUM_WARNING = (
    "ℹ EPS 모멘텀: 과거 스냅샷 데이터가 부족해 현재는 PER 팩터만 유효합니다. "
    "매월 말 데이터가 누적되면 EPS 모멘텀 팩터가 활성화됩니다."
)
_SMA_FILTER_WARNING = (
    "ℹ 하이브리드 모드: SMA 게이트로 일부 종목이 필터링될 수 있습니다."
)

_per_factor = ForwardPerFactor()
_eps_factor = ForwardEpsMomentumFactor()


class HybridFactorSMA(Strategy):
    name = "하이브리드 (펀더멘탈+SMA)"
    description = "팩터로 후보 종목 선별 후 SMA 골든크로스 종목만 보유. Dead-cross 시 중도 청산."
    icon = "🧬"
    tags = ["고급", "하이브리드", "팩터+기술적"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {
        "top_n":      {"type": "int",   "default": 3,   "min": 1,   "max": 20,  "label": "팩터 상위 N"},
        "fast":       {"type": "int",   "default": 10,  "min": 5,   "max": 50,  "label": "SMA Fast"},
        "slow":       {"type": "int",   "default": 50,  "min": 20,  "max": 200, "label": "SMA Slow"},
        "eps_weight": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "EPS 가중"},
        "per_weight": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "PER 가중"},
    }

    def to_backtesting_class(self, params: dict):
        raise NotImplementedError("하이브리드 전략은 portfolio 엔진을 사용합니다")

    def run_portfolio(self, ctx: BacktestContext, params: dict) -> BacktestResult:
        from core.engines.rebalance import monthly_signal_dates, next_trading_day
        import core.repository as repo
        from core.data.fundamentals_provider import fetch_snapshots

        top_n    = int(params.get("top_n", 3))
        fast     = int(params.get("fast", 10))
        slow     = int(params.get("slow", 50))
        eps_w    = float(params.get("eps_weight", 0.5))
        per_w    = float(params.get("per_weight", 0.5))
        commission = ctx.commission

        warns = [_LOOK_AHEAD_WARNING, _EPS_MOMENTUM_WARNING, _SMA_FILTER_WARNING]

        # ── 데이터 준비 ─────────────────────────────────────────────────────────
        if ctx.prices.empty:
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity_curve=empty,
                weights_history=pd.DataFrame(),
                per_ticker_contribution={},
                rebalance_log=[],
                metrics=compute_metrics(empty),
                warnings=warns + ["보유 종목 없음"],
            )

        try:
            close = _get_close(ctx.prices)
        except ValueError as e:
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity_curve=empty,
                weights_history=pd.DataFrame(),
                per_ticker_contribution={},
                rebalance_log=[],
                metrics=compute_metrics(empty),
                warnings=warns + [str(e)],
            )

        close = close.ffill().dropna(how="all")
        if close.empty:
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity_curve=empty,
                weights_history=pd.DataFrame(),
                per_ticker_contribution={},
                rebalance_log=[],
                metrics=compute_metrics(empty),
                warnings=warns + ["종가 데이터 없음"],
            )

        all_tickers   = close.columns.tolist()
        trading_days  = close.index

        # ── fundamentals 스냅샷 ─────────────────────────────────────────────────
        snapshots = fetch_snapshots(all_tickers)
        repo.upsert_fundamentals(snapshots)

        # ── SMA 사전 계산 ────────────────────────────────────────────────────────
        sma_fast = close.rolling(fast).mean()
        sma_slow = close.rolling(slow).mean()

        # ── 월말 시그널 → 진입일 맵핑 ────────────────────────────────────────────
        first_day = trading_days[0]
        rebalance_entries: dict[pd.Timestamp, pd.Timestamp] = {}  # entry → signal
        for sig in monthly_signal_dates(trading_days):
            entry = next_trading_day(sig, trading_days)
            if entry is not None and entry != first_day:
                rebalance_entries[entry] = sig

        # ── SMA 게이트 헬퍼 ──────────────────────────────────────────────────────
        def sma_passes(ticker: str, day: pd.Timestamp) -> bool:
            try:
                f = sma_fast.loc[day, ticker]
                s = sma_slow.loc[day, ticker]
            except KeyError:
                return False
            if pd.isna(f) or pd.isna(s):
                return False
            return float(f) > float(s)

        # ── 팩터 선별 헬퍼 ────────────────────────────────────────────────────────
        def factor_select(tickers: list[str], as_of) -> list[str]:
            per_scores = _per_factor.compute(tickers, as_of)
            eps_scores = _eps_factor.compute(tickers, as_of)
            composite = compose(
                {"forward_per": per_scores, "forward_eps_momentum": eps_scores},
                {"forward_per": per_w, "forward_eps_momentum": eps_w},
            )
            selected = select_top_n(composite, top_n)
            if not selected:
                selected = tickers[:top_n]
            return selected

        # ── 초기 매수 (첫 거래일) ────────────────────────────────────────────────
        initial_candidates = factor_select(all_tickers, first_day.date())
        initial_tickers = [t for t in initial_candidates if sma_passes(t, first_day)]

        shares: dict[str, float] = {}
        cash_pool: float = 0.0

        if initial_tickers:
            if ctx.risk_options is not None:
                from core.engines.risk import compute_weights
                risk_w = compute_weights(
                    initial_tickers, ctx.prices, first_day,
                    ctx.risk_options, ctx.market_index,
                )
                init_weights = risk_w.to_dict()
            else:
                n = len(initial_tickers)
                init_weights = {t: 1.0 / n for t in initial_tickers}

            invested = ctx.cash * (1 - commission)
            for t, w in init_weights.items():
                price = _safe_price(close, first_day, t)
                if price > 0:
                    shares[t] = (invested * w) / price
        else:
            # SMA 통과 종목 없음 → 전액 현금
            cash_pool = ctx.cash

        equity_values: list[float] = []
        weights_records: list[dict] = []
        rebalance_log: list[dict] = []
        pending_liquidations: list[str] = []

        # ── 일별 시뮬레이션 ────────────────────────────────────────────────────────
        for day in trading_days:
            is_rebalance_day = day in rebalance_entries

            if is_rebalance_day:
                # pending 매도는 건너뛰고 전량 월별 리밸런싱으로 처리
                pending_liquidations = []
                sig_date = rebalance_entries[day]

                # 전체 청산 (매도 수수료)
                sell_value = sum(
                    _safe_price(close, day, t) * shares.get(t, 0.0)
                    for t in shares
                )
                proceeds = sell_value * (1 - commission) + cash_pool
                cash_pool = 0.0

                # 팩터 상위 N → SMA 게이트
                candidates = factor_select(all_tickers, sig_date.date())
                passed    = [t for t in candidates if sma_passes(t, day)]
                filtered_out = [t for t in candidates if t not in passed]

                if passed:
                    if ctx.risk_options is not None:
                        from core.engines.risk import compute_weights
                        risk_w = compute_weights(
                            passed, ctx.prices, day,
                            ctx.risk_options, ctx.market_index,
                        )
                        new_weights = risk_w.to_dict()
                    else:
                        n = len(passed)
                        new_weights = {t: 1.0 / n for t in passed}

                    # 재매수
                    shares = {}
                    invest = proceeds * (1 - commission)
                    for t, w in new_weights.items():
                        price = _safe_price(close, day, t)
                        if price > 0:
                            shares[t] = (invest * w) / price
                else:
                    # 통과 종목 없음 → 전액 현금
                    shares = {}
                    cash_pool = proceeds
                    new_weights = {}

                rebalance_log.append({
                    "date": str(day.date()),
                    "signal_date": str(sig_date.date()),
                    "type": "monthly",
                    "holdings": list(shares.keys()),
                    "weights": {t: round(new_weights.get(t, 0.0), 4) for t in shares},
                    "portfolio_value_before": round(sell_value, 0),
                    "sma_filtered_out": filtered_out,
                })

            else:
                # pending 데드-크로스 매도 처리
                if pending_liquidations:
                    sell_tickers = [t for t in pending_liquidations if t in shares]
                    proceeds_dc = 0.0
                    for t in sell_tickers:
                        price = _safe_price(close, day, t)
                        proceeds_dc += price * shares.pop(t) * (1 - commission)
                    if sell_tickers:
                        cash_pool += proceeds_dc
                        rebalance_log.append({
                            "date": str(day.date()),
                            "type": "dead_cross",
                            "tickers_sold": sell_tickers,
                            "proceeds": round(proceeds_dc, 0),
                        })
                    pending_liquidations = []

                # 보유 종목 중 데드-크로스 감지 → 다음 거래일 매도 예약
                new_crosses = [
                    t for t in list(shares.keys())
                    if not sma_passes(t, day)
                ]
                if new_crosses:
                    pending_liquidations = new_crosses

            # ── 일별 자산 가치 ────────────────────────────────────────────────────
            equity = (
                sum(_safe_price(close, day, t) * shares.get(t, 0.0) for t in shares)
                + cash_pool
            )
            equity_values.append(equity)

            # ── 일별 비중 기록 ────────────────────────────────────────────────────
            total_eq = equity if equity > 0 else float("nan")
            w_record: dict[str, float] = {
                t: _safe_price(close, day, t) * shares[t] / total_eq
                for t in shares
            }
            if cash_pool > 0 and equity > 0:
                w_record["cash_weight"] = cash_pool / equity
            weights_records.append(w_record)

        equity_curve  = pd.Series(equity_values, index=trading_days)
        weights_history = pd.DataFrame(weights_records, index=trading_days).fillna(0.0)

        # risk_options의 market_filter가 있으면 항상 cash_weight 컬럼 보장
        if ctx.risk_options is not None and ctx.risk_options.market_filter:
            if "cash_weight" not in weights_history.columns:
                weights_history["cash_weight"] = (
                    1.0 - weights_history.sum(axis=1)
                ).clip(lower=0.0)

        contribution = per_ticker_contribution(
            ctx.prices,
            all_tickers,
            pd.Series({t: 1.0 / len(all_tickers) for t in all_tickers}),
            ctx.cash,
        )

        return BacktestResult(
            equity_curve=equity_curve,
            weights_history=weights_history,
            per_ticker_contribution=contribution,
            rebalance_log=rebalance_log,
            metrics=compute_metrics(equity_curve),
            warnings=warns,
        )


register(HybridFactorSMA())
