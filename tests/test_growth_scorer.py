"""tests/test_growth_scorer.py — 성장주 4팩터 스코어링."""
from __future__ import annotations

import math

import pandas as pd
import pytest


def test_percentile_rank_by_sector_falls_back_for_small_groups():
    from core.scoring.growth_scorer import percentile_rank_by_sector

    values = pd.Series({
        "T1": 10, "T2": 20, "T3": 30, "T4": 40, "T5": 50,
        "E1": 100, "E2": 5,
    })
    sectors = pd.Series({
        "T1": "Tech", "T2": "Tech", "T3": "Tech", "T4": "Tech", "T5": "Tech",
        "E1": "Energy", "E2": "Energy",
    })

    ranked = percentile_rank_by_sector(values, sectors)

    assert ranked["T5"] == pytest.approx(1.0)
    assert ranked["T1"] == pytest.approx(0.2)
    # Energy는 표본 2개라 전체 유니버스 백분위로 fallback.
    assert ranked["E1"] == pytest.approx(1.0)
    assert ranked["E2"] == pytest.approx(1 / 7)


def test_compute_growth_scores_uses_four_factor_weights_and_data_coverage():
    from core.scoring.growth_scorer import compute_growth_scores

    df = pd.DataFrame([
        {
            "ticker": "A", "sector": "Tech", "sales_growth": 0.20, "eps_growth": 0.10,
            "roe": 0.25, "roic": 0.20, "operating_margin": 0.18,
            "fcf_yield": 0.05, "cfo_positive": True,
            "debt_to_equity": 0.4, "current_ratio": 2.0,
        },
        {
            "ticker": "B", "sector": "Tech", "sales_growth": 0.05, "eps_growth": 0.02,
            "roe": 0.10, "roic": 0.08, "operating_margin": 0.08,
            "fcf_yield": 0.01, "cfo_positive": True,
            "debt_to_equity": 1.4, "current_ratio": 1.0,
        },
        {
            "ticker": "C", "sector": "Tech", "sales_growth": None, "eps_growth": None,
            "roe": None, "roic": None, "operating_margin": None,
            "fcf_yield": 0.03, "cfo_positive": True,
            "debt_to_equity": None, "current_ratio": None,
        },
    ]).set_index("ticker")

    scored = compute_growth_scores(df)

    assert scored.loc["A", "growth_composite"] > scored.loc["B", "growth_composite"]
    assert scored.loc["A", "pct_growth"] > scored.loc["B", "pct_growth"]
    assert math.isnan(scored.loc["C", "growth_composite"])
    assert scored.loc["C", "data_coverage"]["factor_count"] == 1


def test_filter_growth_top_requires_all_hard_filter_metrics():
    from core.scoring.growth_scorer import filter_growth_top

    df = pd.DataFrame([
        {
            "ticker": "PASS", "sector": "Tech", "growth_composite": 90.0,
            "debt_to_equity": 0.5, "fcf_yield": 0.03, "operating_cashflow": 100.0,
            "current_ratio": 2.0, "operating_margin": 0.40, "roe": 0.35, "roic": 0.25,
            "market_cap_usd_m": 50_000.0,
        },
        {
            "ticker": "NO_FCF", "sector": "Tech", "growth_composite": 99.0,
            "debt_to_equity": 0.5, "fcf_yield": -0.01, "operating_cashflow": 100.0,
            "current_ratio": 2.0, "operating_margin": 0.31, "roe": 0.30, "roic": 0.20,
            "market_cap_usd_m": 60_000.0,
        },
        {
            "ticker": "MISSING", "sector": "Tech", "growth_composite": 95.0,
            "debt_to_equity": 0.5, "fcf_yield": 0.02, "operating_cashflow": None,
            "current_ratio": 2.0, "operating_margin": 0.32, "roe": 0.30, "roic": 0.20,
            "market_cap_usd_m": 60_000.0,
        },
    ]).set_index("ticker")

    top = filter_growth_top(df, cap="large", market="US", limit=10)

    assert list(top.index) == ["PASS"]
