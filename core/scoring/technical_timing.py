"""EMA20/50/200과 거래량 기반 매수 타이밍 검증."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.data.ohlcv_cache import fetch_ohlcv


def analyze_frame(df: pd.DataFrame) -> dict:
    clean = df[["Open", "Close", "Volume"]].dropna()
    rows = len(clean)
    if rows < 14:
        return {
            "status": "unknown",
            "reason": "RSI 계산에는 최소 14거래일이 필요합니다.",
            "rows": rows,
            "data_sufficiency": _data_sufficiency(rows),
        }

    close = clean["Close"].astype(float)
    latest_close = float(close.iloc[-1])
    latest_open = float(clean["Open"].iloc[-1])
    latest_volume = float(clean["Volume"].iloc[-1])
    has_ema20 = rows >= 20
    has_ema50 = rows >= 50
    has_ema200 = rows >= 200
    has_volume20 = rows >= 21
    latest_ema20 = _latest_ema(close, 20) if has_ema20 else None
    latest_ema50 = _latest_ema(close, 50) if has_ema50 else None
    latest_ema200 = _latest_ema(close, 200) if has_ema200 else None
    avg_volume20 = float(clean["Volume"].iloc[-21:-1].astype(float).mean()) if has_volume20 else None
    volume_ratio = latest_volume / avg_volume20 if avg_volume20 and avg_volume20 > 0 else 0.0
    volume_direction = _volume_direction(latest_open, latest_close)
    volume_level = _volume_level(volume_ratio)
    rsi_series = _wilder_rsi_series(close, 14)
    rsi14 = float(rsi_series.iloc[-1])
    prev_rsi14 = float(rsi_series.iloc[-2]) if len(rsi_series) >= 2 else None
    rsi_level = _rsi_level(rsi14)
    rsi_signal = _rsi_signal(prev_rsi14, rsi14)

    aligned = latest_ema20 > latest_ema50 > latest_ema200 if has_ema20 and has_ema50 and has_ema200 else False
    pullback_stage = _pullback_stage(latest_close, latest_ema20, latest_ema50, latest_ema200)
    pullback = (
        pullback_stage == "approach"
        or pullback_stage == "lower"
    )
    volume_explosion = volume_direction == "bullish" and volume_ratio >= 1.5
    recent_bearish_volume_spike = _has_recent_bearish_volume_spike(clean) if has_volume20 else False
    suitable_candidate = aligned and pullback and volume_direction == "bullish" and volume_ratio >= 1.0

    positive_reasons = []
    warning_reasons = []
    downgrade_reasons = []
    if aligned:
        positive_reasons.append(_reason("aligned", "EMA20 > EMA50 > EMA200 정배열입니다.", "positive"))
    elif not has_ema200:
        warning_reasons.append(_reason("ema200_insufficient", "EMA200은 200일 이동평균이라 최소 200거래일 데이터가 필요합니다.", "warning"))
    if aligned and pullback_stage == "breakdown":
        warning_reasons.append(_reason("pullback_breakdown", "EMA50 아래 3%를 초과해 눌림목보다 이탈에 가깝습니다.", "warning"))
    elif aligned and not pullback:
        warning_reasons.append(_reason("missing_pullback", "상승 추세는 유효하지만 현재가는 EMA20·EMA50 눌림목 범위 밖입니다.", "warning"))
    if pullback:
        message = "현재가가 EMA20·EMA50 아래 0~3% 눌림목 하단입니다." if pullback_stage == "lower" else "현재가가 EMA20·EMA50 눌림목 접근 범위입니다."
        positive_reasons.append(_reason("pullback", message, "positive"))
    if volume_direction == "bullish" and volume_ratio >= 1.0:
        positive_reasons.append(_reason("bullish_volume_increase", "평균 이상 양봉 거래량이 유입되었습니다.", "positive"))
    if aligned and volume_direction == "bullish" and volume_ratio < 1.0:
        warning_reasons.append(_reason("low_bullish_volume", "양봉이지만 20일 평균보다 거래량이 낮아 매수 확인이 부족합니다.", "warning"))
    if rsi_signal == "reclaim_50":
        positive_reasons.append(_reason("rsi_reclaim_50", "RSI가 50선을 아래에서 회복해 모멘텀이 개선됐습니다.", "positive"))
    elif rsi_signal == "lose_50":
        warning_reasons.append(_reason("rsi_lose_50", "RSI가 50선을 이탈해 단기 모멘텀이 약해졌습니다.", "warning"))
    elif rsi_signal == "fading_above_50":
        warning_reasons.append(_reason("rsi_fading_above_50", "RSI는 50 위지만 하락 중이라 모멘텀 둔화를 확인해야 합니다.", "warning"))
    if rsi14 >= 80:
        warning_reasons.append(_reason("extreme_rsi", "RSI가 80 이상으로 극단적 과열 구간입니다.", "warning"))
    if volume_direction == "bearish" and volume_ratio >= 1.0:
        warning_reasons.append(_reason("bearish_volume_increase", "평균 이상 음봉 거래량으로 매도 압력이 감지되었습니다.", "warning"))
    if recent_bearish_volume_spike:
        warning_reasons.append(_reason("recent_bearish_volume_spike", "최근 5거래일 내 강한 음봉 거래량이 감지되었습니다.", "warning"))

    if aligned and pullback:
        downgrade_reasons = [
            _reason(reason["code"], reason["message"], "downgrade")
            for reason in warning_reasons
        ]

    status = (
        "suitable"
        if suitable_candidate and not downgrade_reasons
        else "watch"
        if aligned or not has_ema200
        else "unsuitable"
    )
    return {
        "status": status,
        "reason": None if has_ema200 else "EMA200은 200일 이동평균이라 최소 200거래일 데이터가 필요합니다.",
        "rows": rows,
        "data_sufficiency": _data_sufficiency(rows),
        "aligned": aligned,
        "pullback": pullback,
        "pullback_stage": pullback_stage,
        "volume_explosion": volume_explosion,
        "volume_ratio": volume_ratio,
        "volume_level": volume_level,
        "volume_direction": volume_direction,
        "recent_bearish_volume_spike": recent_bearish_volume_spike,
        "rsi14": rsi14,
        "prev_rsi14": prev_rsi14,
        "rsi_level": rsi_level,
        "rsi_signal": rsi_signal,
        "positive_reasons": positive_reasons,
        "warning_reasons": warning_reasons,
        "downgrade_reasons": downgrade_reasons,
        "close": latest_close,
        "ema20": latest_ema20,
        "ema50": latest_ema50,
        "ema200": latest_ema200,
        "volume": latest_volume,
        "avg_volume20": avg_volume20,
    }


def analyze_timing(ticker: str) -> dict:
    today = date.today()
    df, _ = fetch_ohlcv([ticker], today - timedelta(days=420), today, cache_only=True)
    if df.empty or ticker not in df.columns.get_level_values(0):
        return {"status": "unknown", "reason": "OHLCV 데이터 없음", "rows": 0}
    return analyze_frame(df[ticker])


def _near(value: float, target: float, tolerance: float) -> bool:
    return target > 0 and abs(value - target) / target <= tolerance


def _pullback_stage(close: float, ema20: float | None, ema50: float | None, ema200: float | None) -> str:
    if ema200 is not None and close <= ema200:
        return "breakdown"
    if ema50 is not None and close < ema50 * 0.97:
        return "breakdown"
    if (ema20 is not None and _below_near(close, ema20, 0.03)) or (ema50 is not None and _below_near(close, ema50, 0.03)):
        return "lower"
    if (ema20 is not None and _near(close, ema20, 0.03)) or (ema50 is not None and _near(close, ema50, 0.03)):
        return "approach"
    return "none"


def _latest_ema(close: pd.Series, span: int) -> float:
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def _data_sufficiency(rows: int) -> dict:
    return {
        "price": rows > 0,
        "ema20": rows >= 20,
        "ema50": rows >= 50,
        "ema200": rows >= 200,
        "rsi": rows >= 14,
        "volume": rows >= 21,
    }


def _below_near(value: float, target: float, tolerance: float) -> bool:
    return target > 0 and target * (1 - tolerance) <= value < target


def _volume_level(ratio: float) -> str:
    if ratio < 0.8:
        return "quiet"
    if ratio < 1.0:
        return "normal"
    if ratio < 1.5:
        return "increased"
    if ratio < 2.0:
        return "strong"
    return "explosive"


def _volume_direction(open_: float, close: float) -> str:
    if close > open_:
        return "bullish"
    if close < open_:
        return "bearish"
    return "flat"


def _wilder_rsi(close: pd.Series, period: int) -> float:
    return float(_wilder_rsi_series(close, period).iloc[-1])


def _wilder_rsi_series(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((loss == 0) & (gain <= 0), 50.0)
    return rsi.fillna(50.0)


def _rsi_level(rsi: float) -> str:
    if rsi < 30:
        return "oversold"
    if rsi < 70:
        return "neutral"
    if rsi < 80:
        return "overheated"
    return "extreme_overheated"


def _rsi_signal(prev_rsi: float | None, current_rsi: float) -> str:
    if prev_rsi is None:
        return "unknown"
    if prev_rsi < 50 <= current_rsi:
        return "reclaim_50"
    if prev_rsi >= 50 > current_rsi:
        return "lose_50"
    if current_rsi >= 70:
        return "overheated"
    if current_rsi > 50 and current_rsi < prev_rsi:
        return "fading_above_50"
    if current_rsi > 50 and current_rsi >= prev_rsi:
        return "rising_above_50"
    if current_rsi < 50 and current_rsi > prev_rsi:
        return "recovering_below_50"
    if current_rsi < 50:
        return "weak_below_50"
    return "neutral"


def _has_recent_bearish_volume_spike(clean: pd.DataFrame) -> bool:
    volume = clean["Volume"].astype(float)
    for index in range(len(clean) - 5, len(clean)):
        avg_volume20 = float(volume.iloc[index - 20:index].mean())
        if avg_volume20 <= 0:
            continue
        row = clean.iloc[index]
        if float(row["Close"]) < float(row["Open"]) and float(row["Volume"]) / avg_volume20 >= 1.5:
            return True
    return False


def _reason(code: str, message: str, severity: str) -> dict:
    return {"code": code, "message": message, "severity": severity}
