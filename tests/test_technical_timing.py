"""tests/test_technical_timing.py — EMA20/50/200 기술적 타이밍."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _frame(*, latest_volume: float = 1000, latest_open: float = 99.0, latest_close: float = 100.0) -> pd.DataFrame:
    close = np.full(250, 100.0)
    close[-1] = latest_close
    open_ = close.copy()
    open_[-1] = latest_open
    volume = np.full(250, 1000.0)
    volume[-1] = latest_volume
    return pd.DataFrame({"Open": open_, "Close": close, "Volume": volume})


def test_analyze_frame_returns_partial_indicators_with_less_than_200_rows():
    from core.scoring.technical_timing import analyze_frame

    df = pd.DataFrame({
        "Open": [100.0] * 100,
        "Close": [101.0] * 100,
        "Volume": [1000] * 100,
    })

    result = analyze_frame(df)

    assert result["status"] == "watch"
    assert result["reason"] == "EMA200은 200일 이동평균이라 최소 200거래일 데이터가 필요합니다."
    assert result["rows"] == 100
    assert result["close"] == 101.0
    assert result["ema20"] is not None
    assert result["ema50"] is not None
    assert result["ema200"] is None
    assert result["rsi14"] is not None
    assert result["volume_ratio"] == 1.0
    assert result["data_sufficiency"] == {
        "price": True,
        "ema20": True,
        "ema50": True,
        "ema200": False,
        "rsi": True,
        "volume": True,
    }


def test_analyze_frame_detects_aligned_pullback_and_volume_explosion():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250)
    close[-1] = close[-2] * 1.01
    open_ = close.copy()
    open_[-1] = close[-1] * 0.98
    volume = np.full(250, 1000)
    volume[-1] = 2000
    df = pd.DataFrame({"Open": open_, "Close": close, "Volume": volume})

    result = analyze_frame(df)

    assert result["aligned"] is True
    assert result["pullback"] is True
    assert result["volume_explosion"] is True
    assert result["volume_ratio"] == 2.0
    assert result["volume_level"] == "explosive"
    assert result["volume_direction"] == "bullish"
    assert result["status"] == "watch"
    assert [reason["code"] for reason in result["downgrade_reasons"]] == ["extreme_rsi"]


def test_analyze_frame_classifies_volume_levels_and_direction():
    from core.scoring.technical_timing import analyze_frame

    cases = [
        (700, "quiet"),
        (900, "normal"),
        (1200, "increased"),
        (1700, "strong"),
        (2100, "explosive"),
    ]

    for volume, expected_level in cases:
        result = analyze_frame(_frame(latest_volume=volume))
        assert result["volume_ratio"] == volume / 1000
        assert result["volume_level"] == expected_level
        assert result["volume_direction"] == "bullish"

    assert analyze_frame(_frame(latest_open=101.0))["volume_direction"] == "bearish"
    assert analyze_frame(_frame(latest_open=100.0))["volume_direction"] == "flat"


def test_analyze_frame_uses_wilder_rsi_14():
    from core.scoring.technical_timing import analyze_frame

    close = np.array([100.0 + index * 0.2 + (-1) ** index for index in range(250)])
    df = pd.DataFrame({"Open": close, "Close": close, "Volume": np.full(250, 1000.0)})
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    expected = 100 - (100 / (1 + gain.ewm(alpha=1 / 14, adjust=False).mean() / loss.ewm(alpha=1 / 14, adjust=False).mean()))

    result = analyze_frame(df)

    assert result["rsi14"] == expected.iloc[-1]
    assert result["rsi_level"] == "neutral"


def test_analyze_frame_detects_recent_bearish_volume_spike():
    from core.scoring.technical_timing import analyze_frame

    df = _frame(latest_volume=1100)
    df.loc[df.index[-3], "Open"] = 101.0
    df.loc[df.index[-3], "Close"] = 100.0
    df.loc[df.index[-3], "Volume"] = 1600.0

    result = analyze_frame(df)

    assert result["recent_bearish_volume_spike"] is True
    assert "recent_bearish_volume_spike" in [reason["code"] for reason in result["warning_reasons"]]


def test_analyze_frame_downgrades_suitable_candidate_for_today_bearish_volume():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250)
    close[-1] = close[-2] * 0.99
    open_ = close.copy()
    open_[-1] = close[-1] * 1.01
    volume = np.full(250, 1000)
    volume[-1] = 1100

    result = analyze_frame(pd.DataFrame({"Open": open_, "Close": close, "Volume": volume}))

    assert result["volume_explosion"] is False
    assert result["status"] == "watch"
    assert "bearish_volume_increase" in [reason["code"] for reason in result["downgrade_reasons"]]


def test_analyze_frame_accepts_bullish_volume_at_one_times_average():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250) + np.sin(np.arange(250)) * 2
    open_ = close.copy()
    open_[-1] = close[-1] * 0.995
    volume = np.full(250, 1000.0)

    result = analyze_frame(pd.DataFrame({"Open": open_, "Close": close, "Volume": volume}))

    assert result["volume_ratio"] == 1.0
    assert result["volume_explosion"] is False
    assert result["status"] == "watch"
    assert result["rsi_signal"] == "fading_above_50"
    assert "rsi_fading_above_50" in [reason["code"] for reason in result["downgrade_reasons"]]
    assert [reason["code"] for reason in result["positive_reasons"]] == [
        "aligned",
        "pullback",
        "bullish_volume_increase",
    ]


def test_analyze_frame_treats_rsi_50_reclaim_as_positive():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250) + np.sin(np.arange(250)) * 3
    close[-2] = close[-3] * 0.96
    close[-1] = close[-2] * 1.04
    open_ = close.copy()
    open_[-1] = close[-1] * 0.995
    volume = np.full(250, 1000.0)

    result = analyze_frame(pd.DataFrame({"Open": open_, "Close": close, "Volume": volume}))

    assert result["prev_rsi14"] < 50 <= result["rsi14"]
    assert result["rsi_signal"] == "reclaim_50"
    assert "rsi_reclaim_50" in [reason["code"] for reason in result["positive_reasons"]]


def test_analyze_frame_classifies_pullback_stage():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250)
    open_ = close.copy()
    open_[-1] = close[-1] * 0.99
    volume = np.full(250, 1000.0)
    base = pd.DataFrame({"Open": open_, "Close": close, "Volume": volume})
    base_result = analyze_frame(base)

    near_ema20 = base.copy()
    near_ema20.loc[near_ema20.index[-1], "Close"] = base_result["ema20"] * 1.02
    lower_ema20 = base.copy()
    lower_ema20.loc[lower_ema20.index[-1], "Close"] = base_result["ema20"] * 0.98
    broken_ema50 = base.copy()
    broken_ema50.loc[broken_ema50.index[-1], "Close"] = base_result["ema50"] * 0.96

    assert analyze_frame(near_ema20)["pullback_stage"] == "approach"
    assert analyze_frame(lower_ema20)["pullback_stage"] == "lower"
    assert analyze_frame(broken_ema50)["pullback_stage"] == "breakdown"


def test_analyze_frame_explains_watch_when_pullback_or_volume_is_missing():
    from core.scoring.technical_timing import analyze_frame

    close = np.linspace(100.0, 200.0, 250)
    close[-1] = close[-2] * 1.2
    open_ = close.copy()
    open_[-1] = close[-1] * 0.99
    volume = np.full(250, 1000.0)
    volume[-1] = 700.0

    result = analyze_frame(pd.DataFrame({"Open": open_, "Close": close, "Volume": volume}))

    assert result["status"] == "watch"
    assert "missing_pullback" in [reason["code"] for reason in result["warning_reasons"]]
    assert "low_bullish_volume" in [reason["code"] for reason in result["warning_reasons"]]
