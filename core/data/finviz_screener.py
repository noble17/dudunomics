"""core/data/finviz_screener.py — Finviz 스크리너 bulk fetch.

Finviz 커스텀 뷰(v=152, c=1,2,3,4,5,6,22)에서 EPS Q/Q를 일괄 수집.
컬럼 번호 22 = EPS Q/Q (Qtr over Qtr).
페이지당 행 수는 서버 응답에 따라 동적 결정. S&P 500 기준 ~27 requests.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_BASE = "https://finviz.com/screener"
# v=152: 커스텀 뷰, c=1,2,3,4,5,6,22: ticker + 기본 컬럼 + EPS Q/Q(22번)
_COLUMNS = "1,2,3,4,5,6,22"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_CLIENT = httpx.Client(http2=True, headers=_HEADERS, timeout=15, follow_redirects=True)


def _parse_pct(s: str) -> Optional[float]:
    """'15.23%' → 0.1523, '-3.50%' → -0.035, '-' or '' → None"""
    s = s.strip()
    if not s or s == "-":
        return None
    s = s.replace("%", "")
    try:
        return float(s) / 100.0
    except ValueError:
        return None


def _parse_page(html: str) -> tuple[list[dict], int]:
    """Parse HTML → (rows, total_count).

    Finviz 구조 (2026 리뉴얼 이후):
    - 테이블: table.screener_table
    - 헤더 행: thead > tr > th (Ticker, Company, ..., EPS Q/Q)
    - 데이터 행: tr.styled-row > td (헤더와 동일 순서)
    - 총 개수: div#screener-total 텍스트 "#1 / 503 Total"
    """
    tree = HTMLParser(html)
    rows: list[dict] = []

    # 테이블 헤더 파싱
    table = tree.css_first("table.screener_table")
    if not table:
        log.warning("Finviz screener: screener_table 없음")
        return rows, 0

    header_row = table.css_first("thead tr")
    if not header_row:
        return rows, 0

    headers = [th.text(strip=True) for th in header_row.css("th")]
    try:
        ticker_td_idx = headers.index("Ticker")
        eps_qq_td_idx = headers.index("EPS Q/Q")
    except ValueError:
        log.warning("Finviz screener: Ticker 또는 EPS Q/Q 컬럼 없음. headers=%s", headers)
        return rows, 0

    for tr in table.css("tr.styled-row"):
        tds = tr.css("td")
        if len(tds) <= max(ticker_td_idx, eps_qq_td_idx):
            continue
        ticker = tds[ticker_td_idx].text(strip=True)
        if not ticker:
            continue
        eps_qq_text = tds[eps_qq_td_idx].text(strip=True)
        rows.append({"ticker": ticker, "eps_qq": _parse_pct(eps_qq_text)})

    # 총 개수 파싱: "#1 / 503 Total"
    total = 0
    count_el = tree.css_first("div#screener-total")
    if not count_el:
        count_el = tree.css_first(".count-text")
    if count_el:
        text = count_el.text(strip=True)
        m = re.search(r"/ *([0-9,]+) *Total", text)
        if m:
            try:
                total = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

    return rows, total


def fetch_finviz_bulk(index_filter: str = "idx_sp500") -> dict[str, dict]:
    """Finviz 스크리너에서 전 종목 EPS Q/Q 일괄 수집.

    Returns: {ticker: {"eps_qq": float | None}}
    index_filter: "idx_sp500", "idx_ndx100", "idx_dji" 등
    """
    result: dict[str, dict] = {}
    offset = 1
    total: int | None = None

    while True:
        url = (
            f"{_BASE}?v=152&c={_COLUMNS}"
            f"&f={index_filter}&o=ticker&r={offset}"
        )
        try:
            resp = _CLIENT.get(url)
            resp.raise_for_status()
        except Exception as e:
            log.warning("Finviz bulk fetch 실패 (r=%d): %s", offset, e)
            break

        rows, page_total = _parse_page(resp.text)
        if not rows:
            break

        for row in rows:
            result[row["ticker"]] = {"eps_qq": row["eps_qq"]}

        if total is None:
            total = page_total

        offset += len(rows)
        if total and offset > total:
            break

    log.info("[finviz_bulk] %s: %d종목 수집", index_filter, len(result))
    return result
