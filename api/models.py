# api/models.py
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class HoldingIn(BaseModel):
    name: str
    currency: str       # 'KRW' | 'USD'
    quantity: float
    avg_price: float
    sector: str | None = None
    market: str | None = None   # pykis MARKET_TYPE e.g. 'NASDAQ', 'NYSE', 'KRX'

    @field_validator("currency")
    @classmethod
    def currency_valid(cls, v: str) -> str:
        if v not in ("KRW", "USD"):
            raise ValueError("currency must be KRW or USD")
        return v


class TickerLookupOut(BaseModel):
    ticker: str
    name: str
    market: str
    currency: str


class TickerSearchHit(BaseModel):
    ticker: str
    name: str
    exchange: str
    market: str = ""
    type: str = ""


class HoldingOut(HoldingIn):
    ticker: str
    updated_at: datetime


class CashUpdate(BaseModel):
    cash_krw: float = 0.0
    cash_usd: float = 0.0


class PortfolioRow(BaseModel):
    ticker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    currency: str
    market_value_krw: float
    return_pct: float
    weight_pct: float
    sector: str | None = None


class PortfolioSnapshot(BaseModel):
    rows: list[PortfolioRow]
    total_equity_krw: float
    total_with_cash_krw: float
    total_equity_usd: float
    total_with_cash_usd: float
    cash_krw: float
    cash_usd: float
    usdkrw: float
    updated_at: datetime


class SnapshotHistory(BaseModel):
    ts: datetime
    total_equity_krw: float
    total_with_cash_krw: float
    total_equity_usd: float
    total_with_cash_usd: float


class RiskOptions(BaseModel):
    market_filter: bool = False
    market_filter_index: Literal["auto", "spy", "kospi"] = "auto"
    market_filter_ma_days: int = 200
    market_filter_reduction: float = 0.5
    weighting: Literal["equal", "inverse_vol"] = "equal"
    vol_lookback_days: int = 20


class BacktestRunIn(BaseModel):
    ticker: str | None = None         # 레거시 단일 티커
    tickers: list[str] | None = None  # 1단계 멀티 티커
    strategy: str
    params: dict = {}
    period_start: date
    period_end: date
    risk_options: RiskOptions | None = None

    @model_validator(mode="after")
    def normalize(self) -> "BacktestRunIn":
        if not self.tickers:
            if not self.ticker:
                raise ValueError("ticker 또는 tickers 필수")
            self.tickers = [self.ticker]
        if not self.ticker:
            self.ticker = self.tickers[0]
        return self


class BacktestRunOut(BaseModel):
    id: int
    ticker: str
    strategy: str
    params: dict
    period_start: date
    period_end: date
    total_return: float
    mdd: float
    sharpe: float
    equity_curve: list[dict]
    created_at: datetime
    # 1단계 이후 Optional 필드
    tickers: list[str] | None = None
    cagr: float | None = None
    per_ticker_contribution: dict[str, float] | None = None
    weights_history: list[dict] | None = None
    rebalance_log: list[dict] | None = None
    warnings: list[str] | None = None


class EventIn(BaseModel):
    ts: datetime
    label: str
    amount: int = 0
    type: str = "기타"


class EventOut(EventIn):
    id: int


class FxRateOut(BaseModel):
    pair: str
    rate: float
    ts: datetime | None = None


class StrategiesOut(BaseModel):
    name: str
    params_schema: dict
    engine: str = "backtesting"
    supports_risk_options: bool = False
