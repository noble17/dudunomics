"""Resolve security identifiers from broker statements into app tickers."""
from __future__ import annotations

from functools import lru_cache


_KNOWN_ISIN_MAP: dict[str, dict] = {
    "US02079K3059": {
        "ticker": "GOOGL",
        "name": "Alphabet Inc. Class A",
        "market": "NASDAQ",
        "exchange": "NASDAQ",
    },
    "US02079K1079": {
        "ticker": "GOOG",
        "name": "Alphabet Inc. Class C",
        "market": "NASDAQ",
        "exchange": "NASDAQ",
    },
}


def _market_from_exchange(exchange: str) -> str:
    upper = exchange.upper()
    if "NASDAQ" in upper or upper in ("NMS", "NGM", "NCM"):
        return "NASDAQ"
    if "NYSE" in upper or upper == "NYQ":
        return "NYSE"
    if "AMEX" in upper or "ARCA" in upper or "BATS" in upper or upper in ("ASE", "PCX"):
        return "AMEX"
    return ""


@lru_cache(maxsize=1024)
def resolve_isin(isin: str) -> dict | None:
    """Resolve ISIN through the shared ticker search provider.

    StockAnalysis search accepts many US/KY ISINs directly and returns the
    tradeable ticker. If it fails, callers should keep the row editable.
    """
    query = isin.strip().upper()
    if not query:
        return None
    if query in _KNOWN_ISIN_MAP:
        return _KNOWN_ISIN_MAP[query]
    try:
        from core.data.search_provider import search
        results = search(query, max_results=3)
    except Exception:
        return None

    for row in results:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        return {
            "ticker": ticker,
            "name": row.get("name") or ticker,
            "market": _market_from_exchange(str(row.get("exchange") or "")),
            "exchange": row.get("exchange") or "",
        }
    return None
