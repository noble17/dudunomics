"""tests/test_price_momentum.py"""
from datetime import date
import pandas as pd
import pytest
from unittest.mock import patch


def test_momentum_formula():
    """12-1M = price(t-1M) / price(t-12M) - 1 검증."""
    from core.factors.price_momentum import _compute_12_1m_momentum

    # price 1년 전 100, 1개월 전 120 → momentum = 120/100 - 1 = 0.20
    result = _compute_12_1m_momentum(price_12m_ago=100.0, price_1m_ago=120.0)
    assert abs(result - 0.20) < 1e-9


def test_momentum_returns_nan_on_zero_base():
    from core.factors.price_momentum import _compute_12_1m_momentum
    import math
    result = _compute_12_1m_momentum(price_12m_ago=0.0, price_1m_ago=120.0)
    assert math.isnan(result)
