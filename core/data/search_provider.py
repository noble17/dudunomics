"""
Symbol search: StockAnalysis API (primary) → Yahoo Finance autocomplete (fallback).
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

_CLIENT = httpx.Client(
    timeout=8,
    follow_redirects=True,
    headers={"User-Agent": "dudunomics/1.0"},
)


def search(query: str, max_results: int = 10) -> list[dict]:
    """Search tickers/names. Returns list of {ticker, name, exchange, type}."""
    results = _search_stockanalysis(query, max_results)
    if not results:
        results = _search_yahoo_autocomplete(query, max_results)
    return results


def _search_stockanalysis(query: str, max_results: int) -> list[dict]:
    try:
        url = f"https://stockanalysis.com/api/search?q={query}"
        r = _CLIENT.get(url)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in (data.get("data", {}).get("hits", []) or [])[:max_results]:
            results.append({
                "ticker": item.get("s", ""),
                "name": item.get("n", ""),
                "exchange": item.get("e", ""),
                "type": item.get("t", "stock"),
            })
        return results
    except Exception as e:
        log.debug("stockanalysis search failed: %s", e)
        return []


def _search_yahoo_autocomplete(query: str, max_results: int) -> list[dict]:
    """Fallback: Yahoo Finance autocomplete (same IP pool as yfinance)."""
    try:
        r = _CLIENT.get(
            "https://query2.finance.yahoo.com/v6/finance/autocomplete",
            params={"query": query, "lang": "en"},
        )
        r.raise_for_status()
        items = r.json().get("ResultSet", {}).get("Result", [])[:max_results]
        return [
            {
                "ticker": i.get("symbol", ""),
                "name": i.get("name", ""),
                "exchange": i.get("exchDisp", ""),
                "type": i.get("typeDisp", "stock"),
            }
            for i in items
        ]
    except Exception as e:
        log.debug("yahoo autocomplete failed: %s", e)
        return []


def lookup_meta(ticker: str) -> dict | None:
    """Lookup name and exchange for a single ticker."""
    results = search(ticker, max_results=3)
    for r in results:
        if r.get("ticker", "").upper() == ticker.upper():
            return r
    return results[0] if results else None
