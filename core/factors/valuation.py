"""core/factors/valuation.py — EV/EBITDA + PER 통합 밸류에이션 팩터.

EV/EBITDA(60%) + Forward PER(40%) Winsorize → Z-score 합산.
EV/EBITDA 없는 종목은 PER 단독 z-score.
낮을수록 저평가이므로 백분위 계산 시 ascending=False.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import ClassVar

import pandas as pd
from scipy.stats.mstats import winsorize

from core.factors.base import Factor

log = logging.getLogger(__name__)


def _winsorize_series(s: pd.Series, limits=(0.01, 0.01)) -> pd.Series:
    """NaN 제외 후 윈저라이징, NaN은 원위치 복원."""
    mask = s.notna()
    result = s.copy()
    result[mask] = winsorize(s[mask].values, limits=limits)
    return result


def _zscore_series(s: pd.Series) -> pd.Series:
    """Z-score. std ≈ 0이면 rank 기반 fallback [-1, 1]."""
    std = s.std()
    if std < 1e-6:
        log.warning("Z-score std≈0 — rank fallback 사용")
        return s.rank(pct=True) * 2 - 1
    return (s - s.mean()) / std


def compute_valuation_zscore(
    ev_ebitda: pd.Series,
    fwd_pe: pd.Series,
) -> pd.Series:
    """EV/EBITDA + PER → 통합 밸류에이션 z-score.

    EV/EBITDA 있는 종목: 0.6 × EV/EBITDA_z + 0.4 × PER_z
    EV/EBITDA 없는 종목: PER_z 단독
    """
    pe_clean = fwd_pe.dropna()
    if pe_clean.empty:
        return pd.Series(dtype=float)

    w_pe = _winsorize_series(pe_clean)
    z_pe = _zscore_series(w_pe)

    ev_clean = ev_ebitda.dropna()
    if ev_clean.empty:
        return z_pe.reindex(fwd_pe.index)

    w_ev = _winsorize_series(ev_clean)
    z_ev = _zscore_series(w_ev)

    common = z_pe.index.intersection(z_ev.index)
    pe_only = z_pe.index.difference(common)

    combined = 0.6 * z_ev[common] + 0.4 * z_pe[common]
    result = pd.concat([combined, z_pe[pe_only]])
    return result.reindex(fwd_pe.index)


class ValuationFactor(Factor):
    """배치 외부 단일 종목 조회용. 배치는 universe_scorer 직접 사용."""
    name: ClassVar[str] = "valuation"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        from sqlalchemy import text
        import core.repository as repo

        fwd_pe: dict[str, float] = {}
        ev_ebitda: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                row = s.execute(text("""
                    SELECT raw_fwd_pe, raw_ev_ebitda FROM quant_scores
                    WHERE ticker = :t AND universe = 'sp500'
                    ORDER BY as_of DESC LIMIT 1
                """), {"t": ticker}).fetchone()
                if row:
                    if row[0] is not None and row[0] > 0:
                        fwd_pe[ticker] = row[0]
                    if row[1] is not None and row[1] > 0:
                        ev_ebitda[ticker] = row[1]

        return compute_valuation_zscore(
            pd.Series(ev_ebitda),
            pd.Series(fwd_pe),
        ).reindex(tickers)
