"""Forward 팩터 + 월별 리밸런싱 전략."""
from __future__ import annotations

from datetime import date
from typing import ClassVar

from core.engines.portfolio_engine import BacktestContext, BacktestResult, run_with_rebalance
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

_per_factor = ForwardPerFactor()
_eps_factor = ForwardEpsMomentumFactor()


class FactorRebalance(Strategy):
    name = "Forward 팩터 리밸런싱"
    description = "Forward EPS·PER 팩터로 상위 N개 종목을 선별해 매월 말 리밸런싱. Look-ahead bias 있음."
    icon = "🔬"
    tags = ["펀더멘탈", "월 리밸런싱", "팩터투자"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {
        "top_n": {
            "type": "int", "default": 3, "min": 1, "max": 20, "label": "상위 N",
        },
        "eps_weight": {
            "type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "EPS 모멘텀 가중",
        },
        "per_weight": {
            "type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "PER 가중",
        },
        "rebalance_freq": {
            "type": "enum", "default": "monthly", "options": ["monthly"], "label": "리밸런싱 주기",
        },
    }

    def to_backtesting_class(self, params: dict):
        raise NotImplementedError("Forward 팩터 리밸런싱은 portfolio 엔진을 사용합니다")

    def run_portfolio(self, ctx: BacktestContext, params: dict) -> BacktestResult:
        import core.repository as repo
        from core.data.fundamentals_provider import fetch_snapshots

        top_n = int(params.get("top_n", 3))
        eps_w = float(params.get("eps_weight", 0.5))
        per_w = float(params.get("per_weight", 0.5))

        tickers_all = ctx.prices.columns.get_level_values(0).unique().tolist()

        # 현재 fundamentals 스냅샷 fetch 후 DB 적재
        snapshots = fetch_snapshots(tickers_all)
        repo.upsert_fundamentals(snapshots)

        warns = [_LOOK_AHEAD_WARNING, _EPS_MOMENTUM_WARNING]

        def selector(tickers: list[str], as_of: date) -> dict[str, float]:
            per_scores = _per_factor.compute(tickers, as_of)
            eps_scores = _eps_factor.compute(tickers, as_of)

            composite = compose(
                {"forward_per": per_scores, "forward_eps_momentum": eps_scores},
                {"forward_per": per_w, "forward_eps_momentum": eps_w},
            )

            selected = select_top_n(composite, top_n)
            if not selected:
                selected = tickers[:top_n]

            n = len(selected)
            return {t: 1.0 / n for t in selected}

        return run_with_rebalance(ctx, selector, warns=warns)


register(FactorRebalance())
