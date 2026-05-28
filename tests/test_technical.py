"""tests/test_technical.py"""
import pandas as pd


def test_rsi_calculation():
    from core.factors.technical import _compute_rsi
    # 0부터 1씩 증가하는 가격 시계열 → 모든 diff가 +1, 하락 없음 → RSI ≈ 100
    prices = pd.Series(list(range(29)))  # 0,1,2,...,28 (29 values)
    rsi = _compute_rsi(prices, period=14)
    assert rsi > 90  # 완전 상승 구간


def test_above_ma200():
    from core.factors.technical import _above_ma200
    prices = pd.Series(list(range(1, 202)))  # 201개, 마지막이 201
    result = _above_ma200(prices)
    assert result == True  # 201 > MA200(평균≈101)
