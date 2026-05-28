"""core/factors/forward_eps_momentum.py — Forward EPS 모멘텀 팩터.

1M + 3M EPS 변화율 가중 평균으로 기관 컨센서스 추세를 포착.
1M: 최신 컨센서스 변화, 3M: 추세 지속성. 두 기간 조합으로 노이즈 감쇠.
"""
from __future__ import annotations

from datetime import date
from typing import ClassVar

import pandas as pd
from dateutil.relativedelta import relativedelta

import core.repository as repo
from core.factors.base import Factor


class ForwardEpsMomentumFactor(Factor):
    name: ClassVar[str] = "forward_eps_momentum"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        date_1m = as_of - relativedelta(months=1)
        date_3m = as_of - relativedelta(months=3)
        scores: dict[str, float] = {}

        for ticker in tickers:
            current = repo.get_latest_fundamental(ticker, as_of)
            prev_1m = repo.get_latest_fundamental(ticker, date_1m)
            prev_3m = repo.get_latest_fundamental(ticker, date_3m)

            cur_eps = current.get("forward_eps") if current else None
            eps_1m = prev_1m.get("forward_eps") if prev_1m else None
            eps_3m = prev_3m.get("forward_eps") if prev_3m else None

            slope_1m = (
                (cur_eps - eps_1m) / abs(eps_1m)
                if cur_eps is not None and eps_1m and eps_1m != 0
                else 0.0
            )
            slope_3m = (
                (cur_eps - eps_3m) / abs(eps_3m)
                if cur_eps is not None and eps_3m and eps_3m != 0
                else 0.0
            )
            scores[ticker] = 0.5 * slope_1m + 0.5 * slope_3m

        return pd.Series(scores)
