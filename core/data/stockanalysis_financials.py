"""core/data/stockanalysis_financials.py — stockanalysis.com 연간 재무 스크래퍼.

URL: https://stockanalysis.com/stocks/{ticker}/forecast/
데이터: Revenue(백만달러), EPS
캐시: data/fundamentals_cache.sqlite 의 sa_financials 테이블, 24h TTL.
국내 종목(KS/KQ/T/HK/SS/SZ): None 반환.
"""
from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "fundamentals_cache.sqlite"
_TTL = 86_400  # 24h
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")

_CLIENT = httpx.Client(http2=True, headers=_HEADERS, timeout=15, follow_redirects=True)


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sa_financials "
        "(ticker TEXT PRIMARY KEY, data TEXT, ts REAL)"
    )
    conn.commit()
    return conn


def _from_cache(ticker: str) -> Optional[dict]:
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT data, ts FROM sa_financials WHERE ticker=?", (ticker,)
        ).fetchone()
        conn.close()
        if row and time.time() - row[1] < _TTL:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _to_cache(ticker: str, data: dict) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO sa_financials VALUES (?, ?, ?)",
            (ticker, json.dumps(data), time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_num(s: str) -> Optional[float]:
    s = s.strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "N/A", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_table(tree: HTMLParser, feature: str) -> list[dict]:
    """data-feature='{feature}' 테이블 → [{year, period_end, value, is_estimate}]"""
    table = tree.css_first(f'table[data-feature="{feature}"]')
    if not table:
        return []

    header_row = table.css_first("thead tr")
    if not header_row:
        return []
    # 첫 번째 th는 라벨(e.g., "Revenue") — 제거
    headers = [th.text(strip=True) for th in header_row.css("th")][1:]

    # 첫 번째 tbody tr의 데이터 행
    data_row = table.css_first("tbody tr")
    if not data_row:
        return []
    # 첫 번째 td는 라벨 — 제거
    tds = data_row.css("td")[1:]

    result = []
    for header, td in zip(headers, tds):
        # "FY2024" → year="2024", "FY2025E" → year="2025", is_estimate=True
        is_estimate = header.endswith("E")
        year = header.lstrip("FY").rstrip("E")
        val = _parse_num(td.text(strip=True))
        if val is None:
            continue
        result.append({
            "year": year,
            "period_end": year,
            "value": val,
            "is_estimate": is_estimate,
        })
    return result


def _parse_latest_report_date(tree: HTMLParser) -> Optional[str]:
    """'Last Earnings: May 26, 2026' → '2026.05.26'"""
    for el in tree.css("div, p, span"):
        text = el.text(strip=True)
        if "Last Earnings" in text or "Last earnings" in text:
            span = el.css_first("span")
            if span:
                date_text = span.text(strip=True)
                for fmt in ("%B %d, %Y", "%b %d, %Y"):
                    try:
                        dt = datetime.datetime.strptime(date_text, fmt)
                        return dt.strftime("%Y.%m.%d")
                    except ValueError:
                        continue
    return None


def fetch_annual_financials(ticker: str) -> Optional[dict]:
    """연간 재무 데이터 반환. 국내 종목은 None. 캐시 우선(24h TTL).

    Returns: {
        "revenue":  [{"year", "period_end", "value", "is_estimate"}, ...],
        "eps":      [...],
        "roe":      [],
        "latest_report_date": "YYYY.MM.DD" | None,
    }
    """
    if any(ticker.upper().endswith(s) for s in _SKIP_SUFFIXES):
        return None

    cached = _from_cache(ticker)
    if cached is not None:
        return cached

    try:
        url = f"https://stockanalysis.com/stocks/{ticker.lower()}/forecast/"
        resp = _CLIENT.get(url)
        resp.raise_for_status()
    except Exception as e:
        log.debug("stockanalysis fetch 실패 (%s): %s", ticker, e)
        return None

    tree = HTMLParser(resp.text)
    revenue = _parse_table(tree, "revenue")
    eps = _parse_table(tree, "eps")
    latest_date = _parse_latest_report_date(tree)

    data: dict = {
        "revenue": revenue,
        "eps": eps,
        "roe": [],
        "latest_report_date": latest_date,
    }
    _to_cache(ticker, data)
    return data
