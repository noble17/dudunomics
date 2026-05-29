import math
import numpy as np
import pandas as pd
import pytest
from core.indicators import compute_indicators


def _make_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
    }, index=idx)


def test_compute_indicators_keys():
    df = _make_df(200)
    result = compute_indicators(df)
    assert set(result.keys()) == {"ma", "bollinger", "rsi", "macd", "volume_ma"}
    assert set(result["ma"].keys()) == {"5", "20", "60", "120"}
    assert set(result["bollinger"].keys()) == {"upper", "middle", "lower"}
    assert set(result["macd"].keys()) == {"macd", "signal", "histogram"}


def test_ma5_length_and_format():
    df = _make_df(200)
    result = compute_indicators(df)
    ma5 = result["ma"]["5"]
    # MA5는 처음 4개 NaN이므로 200-4=196개
    assert len(ma5) == 196
    assert "time" in ma5[0]
    assert "value" in ma5[0]
    assert isinstance(ma5[0]["time"], str)
    assert isinstance(ma5[0]["value"], float)


def test_ma120_requires_120_days():
    df = _make_df(200)
    result = compute_indicators(df)
    ma120 = result["ma"]["120"]
    # MA120는 처음 119개 NaN → 200-119=81개
    assert len(ma120) == 81


def test_bollinger_upper_ge_lower():
    df = _make_df(200)
    result = compute_indicators(df)
    for u, l in zip(result["bollinger"]["upper"], result["bollinger"]["lower"]):
        assert u["value"] >= l["value"]


def test_rsi_range():
    df = _make_df(200)
    result = compute_indicators(df)
    for pt in result["rsi"]:
        assert 0 <= pt["value"] <= 100


def test_macd_histogram_equals_macd_minus_signal():
    df = _make_df(200)
    result = compute_indicators(df)
    # 날짜가 같은 포인트들 비교
    macd_map = {pt["time"]: pt["value"] for pt in result["macd"]["macd"]}
    sig_map = {pt["time"]: pt["value"] for pt in result["macd"]["signal"]}
    hist_map = {pt["time"]: pt["value"] for pt in result["macd"]["histogram"]}
    for t in hist_map:
        if t in macd_map and t in sig_map:
            assert abs(hist_map[t] - (macd_map[t] - sig_map[t])) < 1e-6


def test_volume_ma_length():
    df = _make_df(200)
    result = compute_indicators(df)
    # VolumeMA20 → 처음 19개 NaN → 181개
    assert len(result["volume_ma"]) == 181


def test_short_df_returns_empty_for_long_ma():
    """데이터가 50개면 MA120은 빈 리스트."""
    df = _make_df(50)
    result = compute_indicators(df)
    assert result["ma"]["120"] == []
