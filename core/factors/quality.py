"""core/factors/quality.py — 퀄리티 & 지급능력 팩터.

ROE + D/E 역수 결합으로 수익성과 재무 안정성을 동시 평가.
ROE 단독 사용 시 레버리지 과용 기업이 과대평가될 수 있어 부채비율 역수를 결합.
CFO 양수 조건은 이익의 질 검증 — 영업현금흐름이 음수면 이익 조작 가능성.
"""
from __future__ import annotations

import math
from datetime import date
from typing import ClassVar

import pandas as pd

from core.factors.base import Factor


class QualityFactor(Factor):
    name: ClassVar[str] = "quality"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        # universe_scorer가 ExtendedSnapshot 데이터를 직접 전달하는 방식으로 사용됨
        # 여기서는 인터페이스 호환성을 위해 빈 Series 반환
        # 실제 계산은 universe_scorer.py의 _compute_quality_scores()에서 수행
        return pd.Series({t: math.nan for t in tickers})

    @staticmethod
    def score(roe: float | None, debt_to_equity: float | None) -> float:
        """단일 종목 퀄리티 점수 계산.

        debt_to_equity: yfinance 기준 % 단위 (예: 150 = 부채/자본 1.5배)
        ROE=None: 자본잠식 가능성 → 매우 낮은 ROE(-9.99)로 대입해 낮은 점수 부여.
        """
        effective_roe = roe if roe is not None else -9.99
        de_ratio = (debt_to_equity / 100.0) if debt_to_equity is not None else 1.0
        de_ratio = max(de_ratio, 0.01)  # 0 나눗셈 방지
        return 0.6 * effective_roe + 0.4 * (1.0 / de_ratio)
