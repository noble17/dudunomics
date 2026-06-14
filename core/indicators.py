"""기술적 지표 계산 — MA·볼린저밴드·RSI·MACD·VolumeMA."""
from __future__ import annotations

import pandas as pd


def _to_points(index: pd.DatetimeIndex, series: pd.Series) -> list[dict]:
    """NaN 제외, {"time": "YYYY-MM-DD", "value": float} 리스트 반환."""
    return [
        {"time": ts.strftime("%Y-%m-%d"), "value": float(val)}
        for ts, val in zip(index, series)
        if pd.notna(val)
    ]


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    입력: OHLCV DataFrame (index=DatetimeIndex, columns 포함 Open/High/Low/Close/Volume)
    출력: {
        ma: {"5": [...], "20": [...], "50": [...], "120": [...], "200": [...]},
        bollinger: {"upper": [...], "middle": [...], "lower": [...]},
        rsi: [...],
        macd: {"macd": [...], "signal": [...], "histogram": [...]},
        volume_ma: [...],
    }
    각 리스트 원소: {"time": "YYYY-MM-DD", "value": float}
    NaN 구간(워밍업 기간)은 리스트에서 제외.
    """
    close = df["Close"]
    volume = df["Volume"]
    idx = df.index

    # ── MA ──────────────────────────────────────────────────
    ma = {
        str(p): _to_points(idx, close.rolling(p).mean())
        for p in (5, 20, 50, 120, 200)
    }

    # ── 볼린저밴드 (20일, ±2σ) ─────────────────────────────
    bb_middle = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bollinger = {
        "upper": _to_points(idx, bb_middle + 2 * bb_std),
        "middle": _to_points(idx, bb_middle),
        "lower": _to_points(idx, bb_middle - 2 * bb_std),
    }

    # ── RSI (14일, Wilder smoothing) ─────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_series = rsi_series.mask((loss == 0) & (gain > 0), 100.0)
    rsi_series = rsi_series.mask((loss == 0) & (gain <= 0), 50.0).fillna(50.0)
    rsi = _to_points(idx, rsi_series)

    # ── MACD (12/26/9) ────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    macd = {
        "macd": _to_points(idx, macd_line),
        "signal": _to_points(idx, signal_line),
        "histogram": _to_points(idx, histogram),
    }

    # ── VolumeMA (20일) ───────────────────────────────────
    volume_ma = _to_points(idx, volume.rolling(20).mean())

    return {"ma": ma, "bollinger": bollinger, "rsi": rsi, "macd": macd, "volume_ma": volume_ma}
