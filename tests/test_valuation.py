"""tests/test_valuation.py"""
import pandas as pd
import pytest


def test_winsorize_clips_outliers():
    from core.factors.valuation import _winsorize_series
    data = list(range(1, 101)) + [1000.0]
    s = pd.Series(data)
    result = _winsorize_series(s, limits=(0.01, 0.01))
    assert result.max() < 1000.0


def test_zscore_series_mean_zero():
    from core.factors.valuation import _zscore_series
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    result = _zscore_series(s)
    assert abs(result.mean()) < 1e-9


def test_zscore_series_rank_fallback_on_zero_std():
    from core.factors.valuation import _zscore_series
    s = pd.Series([5.0, 5.0, 5.0])
    result = _zscore_series(s)
    assert result is not None


def test_compute_valuation_zscore_uses_ev_ebitda():
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series({"A": 5.0,  "B": 15.0, "C": 30.0})
    pe = pd.Series({"A": 10.0, "B": 20.0, "C": 35.0})
    result = compute_valuation_zscore(ev, pe)
    assert result["A"] < result["C"]


def test_compute_valuation_zscore_fallback_to_per_only():
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series(dtype=float)
    pe = pd.Series({"A": 10.0, "B": 20.0, "C": 30.0})
    result = compute_valuation_zscore(ev, pe)
    assert result["A"] < result["B"] < result["C"]


def test_compute_valuation_zscore_partial_ev_ebitda():
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series({"A": 8.0, "B": 20.0})
    pe = pd.Series({"A": 10.0, "B": 25.0, "C": 12.0})
    result = compute_valuation_zscore(ev, pe)
    assert "C" in result.index
    assert result.notna().all()


def test_dell_scenario():
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series({"DELL": 8.5, "AAPL": 22.0, "MSFT": 28.0, "AMZN": 35.0, "META": 18.0})
    pe = pd.Series({"DELL": 12.0, "AAPL": 28.0, "MSFT": 32.0, "AMZN": 45.0, "META": 22.0})
    result = compute_valuation_zscore(ev, pe)
    assert result["DELL"] == result.min()
