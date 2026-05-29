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
    description: str = ""
    icon: str = "📊"
    tags: list[str] = []


class QuantScoreOut(BaseModel):
    ticker: str
    universe: str
    as_of: date
    company_name: str | None = None
    # 백분위 (0~1)
    pct_momentum: float | None = None
    pct_valuation: float | None = None
    pct_eps_momentum: float | None = None
    pct_quality: float | None = None
    pct_technical: float | None = None
    # Raw 값
    raw_momentum: float | None = None
    raw_fwd_pe: float | None = None
    raw_pbr: float | None = None
    raw_psr: float | None = None
    raw_trailing_pe: float | None = None
    raw_eps_ttm: float | None = None
    raw_fwd_eps: float | None = None
    raw_roe: float | None = None
    raw_debt_ratio: float | None = None
    raw_rsi: float | None = None
    above_ma200: bool | None = None
    cfo_positive: bool | None = None


class TickerNoteIn(BaseModel):
    opinion: str | None = None
    target_price: float | None = None
    memo: str | None = None
    tags: str | None = None


class TickerNoteOut(TickerNoteIn):
    ticker: str
    updated_at: datetime | None = None


class QuoteItem(BaseModel):
    price: float
    change_abs: float
    change_pct: float


class QuotesOut(BaseModel):
    SPY: QuoteItem | None = None
    QQQ: QuoteItem | None = None
    USDKRW: QuoteItem | None = None
    BTC: QuoteItem | None = None


class CandleItem(BaseModel):
    time: str       # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorPoint(BaseModel):
    time: str
    value: float

class IndicatorsData(BaseModel):
    ma: dict[str, list[IndicatorPoint]]
    bollinger: dict[str, list[IndicatorPoint]]
    rsi: list[IndicatorPoint]
    macd: dict[str, list[IndicatorPoint]]
    volume_ma: list[IndicatorPoint]

class CandlesOut(BaseModel):
    ticker: str
    period: str
    candles: list[CandleItem]
    indicators: IndicatorsData | None = None

AlertConditionType = Literal[
    "price_above", "price_below",
    "rsi_above", "rsi_below",
    "ma_golden_cross", "ma_dead_cross",
]

class AlertIn(BaseModel):
    ticker: str
    condition_type: AlertConditionType
    condition_value: float | None = None

class AlertOut(BaseModel):
    id: int
    ticker: str
    condition_type: str
    condition_value: float | None
    enabled: bool
    created_at: datetime

class AlertEventOut(BaseModel):
    id: int
    ticker: str
    condition_type: str
    condition_value: float | None
    triggered_price: float
    triggered_at: datetime
    read: bool


class NewsItem(BaseModel):
    title: str
    published_date: str
    url: str
    site: str
    image: str | None = None


class NewsOut(BaseModel):
    ticker: str
    items: list[NewsItem]


class AISummaryOut(BaseModel):
    ticker: str
    summary: str


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    ticker: str | None = None
