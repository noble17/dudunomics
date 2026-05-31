"""
Fundamentals scraper: Finviz (primary) + StockAnalysis (supplement).
Cache: data/fundamentals_cache.sqlite, 24h TTL.
Only covers US/global equities (KS/KQ/T/HK/SS/SZ skipped upstream).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "fundamentals_cache.sqlite"
_TTL = 86400  # 24h
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}

_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")


@dataclass
class FundamentalsSnapshot:
    ticker: str
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    return_on_equity: Optional[float] = None
    debt_to_equity: Optional[float] = None
    operating_cashflow: Optional[float] = None
    short_name: Optional[str] = None
    # 신규
    ev_ebitda: Optional[float] = None
    peg: Optional[float] = None
    market_cap_m: Optional[float] = None   # 단위: 백만 USD
    capex: Optional[float] = None          # 절댓값 (양수 저장), 단위: USD
    sector: Optional[str] = None
    industry: Optional[str] = None
    negative_book_value: bool = False


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (ticker TEXT PRIMARY KEY, data TEXT, ts REAL)"
    )
    conn.commit()
    return conn


def _from_cache(ticker: str) -> Optional[FundamentalsSnapshot]:
    try:
        conn = _get_db()
        row = conn.execute("SELECT data, ts FROM cache WHERE ticker=?", (ticker,)).fetchone()
        conn.close()
        if row and time.time() - row[1] < _TTL:
            d = json.loads(row[0])
            return FundamentalsSnapshot(**d)
    except Exception:
        pass
    return None


def _to_cache(snap: FundamentalsSnapshot) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
            (snap.ticker, json.dumps(dataclasses.asdict(snap)), time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_num(s: str) -> Optional[float]:
    if not s:
        return None
    s = s.strip().replace(",", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_market_cap_m(s: str) -> Optional[float]:
    """Market Cap 문자열 → 백만 USD 단위 float. 예: '45.2B' → 45200.0"""
    if not s:
        return None
    s = s.strip().replace(",", "")
    for suffix, mult in [("T", 1_000_000), ("B", 1_000), ("M", 1), ("K", 0.001)]:
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except ValueError:
                return None
    try:
        return float(s) / 1_000_000
    except ValueError:
        return None


_CLIENT = httpx.Client(
    http2=True,
    headers=_HEADERS,
    timeout=12,
    follow_redirects=True,
)


def _fetch_finviz(ticker: str) -> FundamentalsSnapshot:
    snap = FundamentalsSnapshot(ticker=ticker)
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
        r = _CLIENT.get(url)
        r.raise_for_status()
        tree = HTMLParser(r.text)
        # Finviz snapshot table: key-value pairs
        cells = tree.css("table.snapshot-table2 td")
        kv: dict[str, str] = {}
        for i in range(0, len(cells) - 1, 2):
            k = cells[i].text(strip=True)
            v = cells[i + 1].text(strip=True)
            kv[k] = v
        snap.forward_pe = _parse_num(kv.get("Forward P/E", ""))
        snap.trailing_pe = _parse_num(kv.get("P/E", ""))
        # P/B: "-"이면 자본잠식 플래그
        raw_pb = kv.get("P/B", "").strip()
        if raw_pb == "-":
            snap.negative_book_value = True
            snap.price_to_book = None
        else:
            snap.price_to_book = _parse_num(raw_pb)
            snap.negative_book_value = False
        snap.price_to_sales = _parse_num(kv.get("P/S", ""))
        snap.forward_eps = _parse_num(kv.get("EPS next Y", ""))
        snap.trailing_eps = _parse_num(kv.get("EPS", ""))
        snap.return_on_equity = _parse_num(kv.get("ROE", ""))
        snap.debt_to_equity = _parse_num(kv.get("Debt/Eq", ""))
        # 신규
        snap.ev_ebitda = _parse_num(kv.get("EV/EBITDA", ""))
        snap.peg = _parse_num(kv.get("PEG", ""))
        snap.market_cap_m = _parse_market_cap_m(kv.get("Market Cap", ""))
        # sector/industry: snapshot-table2 kv 우선, 없으면 상단 div 탐색
        if kv.get("Sector"):
            snap.sector = kv.get("Sector") or None
            snap.industry = kv.get("Industry") or None
        else:
            sector_div = tree.css_first('div[class*="space-x-0.5"][class*="overflow-hidden"]')
            if sector_div:
                tab_links = [a.text(strip=True) for a in sector_div.css("a.tab-link") if a.text(strip=True)]
                snap.sector = tab_links[0] if len(tab_links) >= 1 else None
                snap.industry = tab_links[1] if len(tab_links) >= 2 else None
        # short name from h2 heading (finviz page structure)
        title_el = tree.css_first("h2")
        if title_el:
            snap.short_name = title_el.text(strip=True)
    except Exception as e:
        log.debug("finviz fetch failed for %s: %s", ticker, e)
    return snap


def _supplement_stockanalysis(snap: FundamentalsSnapshot) -> None:
    """Fill in missing operating_cashflow and capex from stockanalysis.com."""
    if snap.operating_cashflow is not None and snap.capex is not None:
        return
    try:
        url = f"https://stockanalysis.com/stocks/{snap.ticker.lower()}/financials/cash-flow-statement/"
        r = _CLIENT.get(url)
        r.raise_for_status()
        tree = HTMLParser(r.text)

        def _parse_cf_value(raw: str) -> Optional[float]:
            raw = raw.strip()
            if raw.startswith("(") and raw.endswith(")"):
                raw = "-" + raw[1:-1]
            for suffix, exp in (("T", "e12"), ("B", "e9"), ("M", "e6"), ("K", "e3")):
                if raw.endswith(suffix):
                    raw = raw[:-1] + exp
                    break
            return _parse_num(raw)

        for row in tree.css("tr"):
            cells = row.css("td")
            if not cells:
                continue
            label = cells[0].text(strip=True).lower()
            value = cells[1].text(strip=True) if len(cells) > 1 else ""

            if snap.operating_cashflow is None and "operating" in label and "cash" in label:
                snap.operating_cashflow = _parse_cf_value(value)

            if snap.capex is None and (
                "capital expenditure" in label
                or "capex" in label
                or ("purchase" in label and "property" in label)
            ):
                v = _parse_cf_value(value)
                snap.capex = abs(v) if v is not None else None

            if snap.operating_cashflow is not None and snap.capex is not None:
                break
    except Exception as e:
        log.debug("stockanalysis supplement failed for %s: %s", snap.ticker, e)


def fetch_fundamentals(ticker: str) -> Optional[FundamentalsSnapshot]:
    """Fetch fundamentals from Finviz + StockAnalysis. Returns None if both fail or ticker is non-US."""
    if any(ticker.upper().endswith(sfx) for sfx in _SKIP_SUFFIXES):
        return None
    cached = _from_cache(ticker)
    if cached:
        return cached
    snap = _fetch_finviz(ticker)
    _supplement_stockanalysis(snap)
    _to_cache(snap)
    # Return None if all numeric fields are None (both sources failed entirely)
    numeric_fields = (
        "forward_pe", "trailing_pe", "price_to_book", "price_to_sales",
        "forward_eps", "trailing_eps", "return_on_equity", "debt_to_equity",
        "operating_cashflow",
    )
    if all(getattr(snap, f) is None for f in numeric_fields):
        return None
    return snap
