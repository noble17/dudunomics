"""Equal Weight Buy & Hold 전략."""
from __future__ import annotations

from typing import ClassVar

from core.strategies.base import Strategy, register
from core.engines.portfolio_engine import BacktestContext, BacktestResult, run_equal_weight_buy_hold


class EqualWeight(Strategy):
    name = "Equal Weight"
    description = "여러 종목에 동일한 비중으로 분산 투자하고 Buy & Hold. 리밸런싱 없이 단순하게 장기 보유."
    icon = "⚖️"
    tags = ["다종목", "초보 친화적", "분산투자"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {}

    def to_backtesting_class(self, params: dict):
        raise NotImplementedError("Equal Weight는 portfolio 엔진을 사용합니다")

    def run_portfolio(self, ctx: BacktestContext, params: dict) -> BacktestResult:
        return run_equal_weight_buy_hold(ctx)


register(EqualWeight())
