"""공통 종목 데이터 조회/보강 서비스."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from core import repository as repo
from core.data.normalization import normalize_finite_numbers
from core.data.ohlcv_cache import fetch_ohlcv


def get_price_history(ticker: str, start: date, end: date) -> dict:
    ticker = ticker.upper()
    prices, warnings = fetch_ohlcv([ticker], start, end, cache_only=True)
    candles = []
    if not prices.empty and ticker in prices.columns.get_level_values(0):
        df = prices[ticker][["Open", "High", "Low", "Close", "Volume"]].dropna()
        candles = [
            {
                "time": ts.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
            for ts, row in df.iterrows()
        ]
    return {"ticker": ticker, "start": start, "end": end, "candles": candles, "warnings": warnings}


def get_fundamentals(ticker: str, universe: str = "sp500") -> dict:
    ticker = ticker.upper()
    snapshot = repo.get_latest_fundamental_snapshot(ticker)
    if snapshot:
        return normalize_finite_numbers({
            "ticker": ticker,
            "universe": universe,
            "valuation_source": snapshot.get("source"),
            "valuation_as_of": snapshot.get("as_of"),
            "peg": snapshot.get("peg"),
            "forward_pe": snapshot.get("forward_pe"),
            "psr": snapshot.get("psr"),
            "forward_eps": snapshot.get("forward_eps"),
            "forward_revenue_growth": snapshot.get("revenue_growth"),
            "forward_eps_growth": snapshot.get("eps_growth"),
            "pbr": snapshot.get("pbr"),
            "per": snapshot.get("per"),
            "roe": snapshot.get("roe"),
            "roic": snapshot.get("roic"),
            "market_cap": snapshot.get("market_cap"),
            "fallback_used": True,
        })

    row = repo.get_quant_ticker(ticker, universe)
    return normalize_finite_numbers({
        "ticker": ticker,
        "universe": universe,
        "valuation_source": "BATCH" if row else None,
        "valuation_as_of": row.get("as_of") if row else None,
        "peg": row.get("raw_peg") if row else None,
        "forward_pe": row.get("raw_fwd_pe") if row else None,
        "psr": row.get("raw_psr") if row else None,
        "forward_eps": row.get("raw_fwd_eps") if row else None,
        "forward_revenue_growth": row.get("raw_fwd_rev_growth") if row else None,
        "forward_eps_growth": row.get("raw_fwd_eps_growth") if row else None,
        "pbr": row.get("raw_pbr") if row else None,
        "per": row.get("raw_trailing_pe") if row else None,
        "roe": row.get("raw_roe") if row else None,
        "roic": row.get("raw_roic") if row else None,
        "market_cap": row.get("raw_market_cap_usd_m") if row else None,
        "fallback_used": False,
    })


def get_data_status(ticker: str) -> list[dict]:
    return repo.get_ticker_data_status(ticker.upper())


def hydrate_ticker_data(ticker: str, scopes: list[str] | None = None) -> dict:
    ticker = ticker.upper()
    scopes = scopes or ["ohlcv"]
    warnings: list[str] = []
    if "ohlcv" in scopes:
        today = date.today()
        start = today - timedelta(days=420)
        prices, fetch_warnings = fetch_ohlcv([ticker], start, today, force=True)
        warnings.extend(fetch_warnings)
        _update_ohlcv_status(ticker, prices, fetch_warnings)
    return {"ticker": ticker, "scopes": scopes, "warnings": warnings, "status": get_data_status(ticker)}


def _update_ohlcv_status(ticker: str, prices: pd.DataFrame, warnings: list[str]) -> None:
    now = datetime.now()
    min_date = None
    max_date = None
    rows = 0
    if not prices.empty and ticker in prices.columns.get_level_values(0):
        frame = prices[ticker].dropna(how="all")
        if not frame.empty:
            min_date = frame.index.min().date()
            max_date = frame.index.max().date()
            rows = len(frame)
    repo.upsert_ticker_data_status({
        "ticker": ticker,
        "data_type": "ohlcv",
        "source": "kis",
        "min_date": min_date,
        "max_date": max_date,
        "last_fetched_at": now,
        "last_success_at": now if rows else None,
        "last_error": "; ".join(warnings) if warnings else None,
        "coverage_json": {"rows": rows},
    })
