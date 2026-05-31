# core/data/market_indices.py
"""시장 지표 — DJI/VIX/US10Y/WTI/GOLD 현재 시세.

소스:
- DJI, VIX, GOLD: FMP /stable/quote (FMP_API_KEY 필요)
- US10Y: FMP /stable/treasury-rates (FMP_API_KEY 필요)
- WTI: Stooq /q/l/ CSV (인증 불필요)
"""
from __future__ import annotations

import csv
import io
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_FMP_BASE = "https://financialmodelingprep.com/stable"
_STOOQ_URL = "https://stooq.com/q/l/"
_TTL = 300.0  # 5분

_cache: dict[str, tuple[dict, float]] = {}


def _fetch_fmp_quote(symbol: str) -> dict | None:
    """FMP /stable/quote — 단일 심볼. {"price": float, "change_pct": float} or None."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return None

    cache_key = f"fmp:{symbol}"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            f"{_FMP_BASE}/quote",
            params={"symbol": symbol, "apikey": api_key},
            timeout=8,
        )
        r.raise_for_status()
        items = r.json()
        if not items:
            return None
        item = items[0]
        result: dict = {
            "price": float(item["price"]),
            "change_pct": round(float(item.get("changePercentage") or 0.0), 4),
        }
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("FMP quote 실패 (%s): %s", symbol, e)
        return None


def _fetch_fmp_treasury_10y() -> dict | None:
    """FMP /stable/treasury-rates → year10 수익률. {"price": float, "change_pct": float} or None."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return None

    cache_key = "fmp:treasury10y"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            f"{_FMP_BASE}/treasury-rates",
            params={"apikey": api_key},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        today_val = float(rows[0]["year10"])
        change_pct = 0.0
        if len(rows) >= 2 and rows[1].get("year10"):
            prev_val = float(rows[1]["year10"])
            if prev_val:
                change_pct = round((today_val - prev_val) / prev_val * 100, 4)
        result: dict = {"price": today_val, "change_pct": change_pct}
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("FMP treasury-rates 실패: %s", e)
        return None


def _fetch_stooq_wti() -> dict | None:
    """Stooq CL.F → WTI 현재가. {"price": float, "change_pct": float} or None."""
    cache_key = "stooq:cl.f"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            _STOOQ_URL,
            params={"s": "cl.f", "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            timeout=8,
        )
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        row = next(reader, None)
        if not row:
            return None
        close = float(row["Close"])
        open_ = float(row["Open"]) if row.get("Open") else close
        change_pct = round((close - open_) / open_ * 100, 4) if open_ else 0.0
        result: dict = {"price": close, "change_pct": change_pct}
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("Stooq WTI 실패: %s", e)
        return None


def get_market_indices() -> dict[str, dict | None]:
    """DJI, VIX, US10Y, WTI, GOLD 현재 시세 반환.

    Returns:
        {
            "DJI":   {"price": float, "change_pct": float} | None,
            "VIX":   {"price": float, "change_pct": float} | None,
            "US10Y": {"price": float, "change_pct": float} | None,
            "WTI":   {"price": float, "change_pct": float} | None,
            "GOLD":  {"price": float, "change_pct": float} | None,
        }
    """
    return {
        "DJI":   _fetch_fmp_quote("^DJI"),
        "VIX":   _fetch_fmp_quote("^VIX"),
        "GOLD":  _fetch_fmp_quote("GCUSD"),
        "US10Y": _fetch_fmp_treasury_10y(),
        "WTI":   _fetch_stooq_wti(),
    }
