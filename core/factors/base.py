"""Factor ABC."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import ClassVar

import pandas as pd


class Factor(ABC):
    name: ClassVar[str]

    @abstractmethod
    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        """ticker → score (높을수록 선호). NaN 허용."""
        ...
