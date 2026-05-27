"""Strategy ABC + Registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from core.engines.portfolio_engine import BacktestContext, BacktestResult


class Strategy(ABC):
    name: ClassVar[str]
    params_schema: ClassVar[dict]       # {"param_name": {"type": "int", "default": 20, "label": "...", "min": 1, "max": 200}}
    engine: ClassVar[str] = "backtesting"       # "backtesting" | "portfolio"
    supports_risk_options: ClassVar[bool] = False
    description: ClassVar[str] = ""
    icon: ClassVar[str] = "📊"
    tags: ClassVar[list[str]] = []

    @abstractmethod
    def to_backtesting_class(self, params: dict):
        """backtesting.py Strategy 클래스를 반환한다."""
        ...

    def run_portfolio(self, ctx: "BacktestContext", params: dict) -> "BacktestResult":
        """portfolio 엔진 전략 실행. engine="portfolio" 전략이 구현한다."""
        raise NotImplementedError(f"{self.name}은 portfolio 엔진을 지원하지 않습니다")


_registry: dict[str, Strategy] = {}


def register(strategy: Strategy):
    _registry[strategy.name] = strategy


def get_strategy(name: str) -> Strategy:
    if name not in _registry:
        raise KeyError(f"전략 없음: {name}")
    return _registry[name]


def list_strategies() -> list[dict]:
    return [
        {
            "name": s.name,
            "params_schema": s.params_schema,
            "engine": s.engine,
            "supports_risk_options": s.supports_risk_options,
            "description": s.description,
            "icon": s.icon,
            "tags": s.tags,
        }
        for s in _registry.values()
    ]
