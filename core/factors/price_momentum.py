"""core/factors/price_momentum.py — 12-1M 가격 모멘텀 팩터.

12-1M 정의: price(t-1M) / price(t-12M) - 1
단기 1개월을 제거해 Mean Reversion 노이즈를 차단한다.
(Jegadeesh & Titman, 1993 / Fama-French momentum anomaly)
"""
from __future__ import annotations

import math
import logging
from datetime import date
from typing import ClassVar

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import text

import core.repository as repo
from core.factors.base import Factor

log = logging.getLogger(__name__)


def _compute_12_1m_momentum(price_12m_ago: float, price_1m_ago: float) -> float:
    """12-1M 모멘텀 계산."""
    if price_12m_ago == 0:
        return math.nan
    return price_1m_ago / price_12m_ago - 1


class PriceMomentumFactor(Factor):
    name: ClassVar[str] = "price_momentum"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        date_12m = as_of - relativedelta(months=12)
        date_1m = as_of - relativedelta(months=1)
        scores: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                # prices_cache에서 가장 가까운 거래일 종가 조회 (12개월 전)
                r12 = s.execute(text("""
                    SELECT close FROM prices_cache
                    WHERE ticker = :t AND date <= :d
                    ORDER BY date DESC LIMIT 1
                """), {"t": ticker, "d": date_12m}).fetchone()

                # prices_cache에서 가장 가까운 거래일 종가 조회 (1개월 전)
                r1 = s.execute(text("""
                    SELECT close FROM prices_cache
                    WHERE ticker = :t AND date <= :d
                    ORDER BY date DESC LIMIT 1
                """), {"t": ticker, "d": date_1m}).fetchone()

                if r12 and r1 and r12[0] and r1[0]:
                    scores[ticker] = _compute_12_1m_momentum(r12[0], r1[0])
                else:
                    scores[ticker] = math.nan

        return pd.Series(scores)
