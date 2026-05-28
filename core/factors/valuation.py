"""core/factors/valuation.py — 통합 밸류에이션 팩터.

Forward PER + PBR을 Winsorizing 후 Z-score 합산.
낮을수록 저평가이므로 백분위 계산 시 역수 처리(1 - pct).

Winsorizing: 극단 아웃라이어(PER 수천배 기업)가 유니버스 Z-score를
            왜곡하는 것을 막기 위해 1%·99% 분위수로 강제 클리핑.
Rank Fallback: std ≈ 0인 엣지 케이스에서 rank 기반 표준화로 전환.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import ClassVar

import numpy as np
import pandas as pd
from scipy.stats.mstats import winsorize

from core.factors.base import Factor
import core.repository as repo

log = logging.getLogger(__name__)


def _winsorize_series(s: pd.Series, limits=(0.01, 0.01)) -> pd.Series:
    """NaN 제외 후 윈저라이징, NaN은 원위치 복원."""
    mask = s.notna()
    result = s.copy()
    result[mask] = winsorize(s[mask].values, limits=limits)
    return result


def _combined_value_zscore(
    fwd_pe: pd.Series,
    pbr: pd.Series,
) -> pd.Series:
    """PER + PBR Winsorize → Z-score → 평균. 낮을수록 저평가."""
    w_pe = _winsorize_series(fwd_pe)
    w_pbr = _winsorize_series(pbr)

    def to_zscore(s: pd.Series) -> pd.Series:
        std = s.std()
        if std < 1e-6:
            # Fallback: rank 기반 표준화 [-1, 1] 범위
            # std ≈ 0은 모든 종목이 동일 값인 엣지 케이스 (적자 전환 후 PE 일괄 결측 등)
            log.warning("Z-score std≈0 — rank fallback 사용")
            r = s.rank(pct=True)
            return r * 2 - 1
        return (s - s.mean()) / std

    combined = (to_zscore(w_pe) + to_zscore(w_pbr)) / 2
    return combined


class ValuationFactor(Factor):
    name: ClassVar[str] = "valuation"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        from sqlalchemy import text

        fwd_pe: dict[str, float] = {}
        pbr: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                row = s.execute(text("""
                    SELECT raw_fwd_pe, raw_pbr FROM quant_scores
                    WHERE ticker = :t AND universe = 'sp500'
                    ORDER BY as_of DESC LIMIT 1
                """), {"t": ticker}).fetchone()
                if row:
                    if row[0] is not None and row[0] > 0:
                        fwd_pe[ticker] = row[0]
                    if row[1] is not None and row[1] > 0:
                        pbr[ticker] = row[1]

        pe_s = pd.Series(fwd_pe)
        pbr_s = pd.Series(pbr)
        common = pe_s.index.intersection(pbr_s.index)
        if common.empty:
            return pd.Series({t: float("nan") for t in tickers})

        combined = _combined_value_zscore(pe_s[common], pbr_s[common])
        return combined.reindex(tickers)
