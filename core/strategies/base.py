"""Strategy ABC + Registry."""
from abc import ABC, abstractmethod
from typing import ClassVar


class Strategy(ABC):
    name: ClassVar[str]
    params_schema: ClassVar[dict]   # {"param_name": {"type": "int", "default": 20, "label": "...", "min": 1, "max": 200}}

    @abstractmethod
    def to_backtesting_class(self, params: dict):
        """backtesting.py Strategy 클래스를 반환한다."""
        ...


_registry: dict[str, Strategy] = {}


def register(strategy: Strategy):
    _registry[strategy.name] = strategy


def get_strategy(name: str) -> Strategy:
    if name not in _registry:
        raise KeyError(f"전략 없음: {name}")
    return _registry[name]


def list_strategies() -> list[dict]:
    return [{"name": s.name, "params_schema": s.params_schema} for s in _registry.values()]
