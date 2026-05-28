"""core/factors/technical.py — 기술적 지표 팩터.

RSI(14): 유니버스 내 백분위 순위로 변환.
  단순 rsi/100 정규화는 RSI 60~70의 강한 상승 종목을 중립 취급하는 문제가 있어,
  유니버스 상대 백분위로 모멘텀 강도를 반영한다.
200일 MA: 기관 장기 추세 기준선. 하회 시 기관 매수세 유입 불리.
"""
from __future__ import annotations

import math
import logging
from datetime import date, timedelta
from typing import ClassVar

import pandas as pd
from sqlalchemy import text

import core.repository as repo
from core.factors.base import Factor

log = logging.getLogger(__name__)


def _compute_rsi(price_series: pd.Series, period: int = 14) -> float:
    """단일 종목 RSI 계산. price_series는 종가 시계열."""
    if len(price_series) < period + 1:
        return math.nan
    delta = price_series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()

    # loss가 0인 경우 (하락이 없음), RSI = 100
    # loss가 0이 아닌 경우, 표준 RSI 공식 적용
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if not math.isnan(val) else math.nan


def _above_ma200(price_series: pd.Series) -> bool:
    """현재 종가가 200일 단순이동평균 위인지 여부."""
    if len(price_series) < 200:
        return False
    ma200 = price_series.iloc[-200:].mean()
    return float(price_series.iloc[-1]) > ma200


class TechnicalFactor(Factor):
    name: ClassVar[str] = "technical"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        # universe_scorer에서 직접 계산하므로 stub
        return pd.Series({t: math.nan for t in tickers})

    @staticmethod
    def compute_raw(ticker: str, as_of: date) -> dict:
        """단일 종목 RSI + MA200 계산. 결과: {rsi, above_ma200}"""
        start = as_of - timedelta(days=300)
        with repo.session() as s:
            rows = s.execute(text("""
                SELECT date, close FROM prices_cache
                WHERE ticker = :t AND date >= :start AND date <= :as_of
                ORDER BY date ASC
            """), {"t": ticker, "start": start, "as_of": as_of}).fetchall()

        if not rows:
            return {"rsi": math.nan, "above_ma200": False}

        prices = pd.Series([r[1] for r in rows], dtype=float)
        return {
            "rsi": _compute_rsi(prices, period=14),
            "above_ma200": _above_ma200(prices),
        }
