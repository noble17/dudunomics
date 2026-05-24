"""PriceProvider ABC."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Price:
    ticker: str
    current: float
    currency: str       # 'KRW' | 'USD'
    change_pct: float | None = None


class PriceProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Price: ...

    @abstractmethod
    def get_current_prices(self, tickers: list[str]) -> dict[str, Price]: ...
