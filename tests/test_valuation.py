"""tests/test_valuation.py"""
import numpy as np
import pandas as pd


def test_winsorize_clips_outliers():
    from core.factors.valuation import _winsorize_series
    # 1% 윈저라이징은 최소 100개 이상의 데이터 필요
    data = list(range(1, 101)) + [1000.0]  # 1-100 + 1000 (상위 1% 아웃라이어)
    s = pd.Series(data)
    result = _winsorize_series(s, limits=(0.01, 0.01))
    assert result.max() < 1000.0


def test_zscore_combines_pe_pbr():
    from core.factors.valuation import _combined_value_zscore
    pe = pd.Series([10.0, 20.0, 30.0], index=["A", "B", "C"])
    pbr = pd.Series([1.0, 2.0, 3.0], index=["A", "B", "C"])
    result = _combined_value_zscore(pe, pbr)
    # 낮은 PER/PBR인 A가 가장 낮은 z-score여야 함 (역수 처리 전)
    assert result["A"] < result["C"]


def test_fallback_rank_on_near_zero_std():
    from core.factors.valuation import _combined_value_zscore
    # 모든 값이 같으면 std=0 → rank fallback
    pe = pd.Series([10.0, 10.0, 10.0], index=["A", "B", "C"])
    pbr = pd.Series([2.0, 2.0, 2.0], index=["A", "B", "C"])
    result = _combined_value_zscore(pe, pbr)
    assert result is not None  # fallback이 crash하지 않음
