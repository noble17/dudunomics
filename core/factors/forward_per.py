"""Forward PER 역수 팩터 — 낮은 PER = 높은 점수 (1/forward_pe)."""
from __future__ import annotations

from datetime import date
from typing import ClassVar

import pandas as pd

import core.repository as repo
from core.factors.base import Factor


class ForwardPerFactor(Factor):
    name: ClassVar[str] = "forward_per"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        scores: dict[str, float] = {}
        for ticker in tickers:
            row = repo.get_latest_fundamental(ticker, as_of)
            fpe = row.get("forward_pe") if row else None
            if fpe and fpe > 0:
                scores[ticker] = 1.0 / fpe
            else:
                scores[ticker] = float("nan")
        return pd.Series(scores)
