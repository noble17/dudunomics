"""core/data/stockanalysis_financials.py — stockanalysis.com 연간 재무 스크래퍼.

stockanalysis.com은 SvelteKit CSR이므로 <script> 블록에 embed된
JS object literal에서 데이터를 파싱한다.

구조: table:{annual:{eps:[...], dates:[...], revenue:[...], analysts:[...]}}
- revenue: 절대달러 → 백만달러로 변환
- is_estimate: analysts[i] is not null
- "[PRO]" / null → 제외

URL: https://stockanalysis.com/stocks/{ticker}/forecast/
캐시: data/fundamentals_cache.sqlite 의 sa_financials 테이블, 24h TTL.
국내 종목(KS/KQ/T/HK/SS/SZ): None 반환.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "fundamentals_cache.sqlite"
_TTL = 86_400  # 24h
_CACHE_VER = 3
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")

_CLIENT = httpx.Client(http2=True, headers=_HEADERS, timeout=15, follow_redirects=True)


# ── 캐시 ──────────────────────────────────────────────────────────────────────

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
            cached = json.loads(row[0])
            if cached.get("_v") == _CACHE_VER:
                # ROE가 빈 배열인데 revenue/eps 데이터가 있으면 부분 실패 → 재페치
                if not cached.get("roe") and (cached.get("revenue") or cached.get("eps")):
                    return None
                return cached
    except Exception:
        pass
    return None


def _to_cache(ticker: str, data: dict) -> None:
    try:
        payload = {**data, "_v": _CACHE_VER}
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO sa_financials VALUES (?, ?, ?)",
            (ticker, json.dumps(payload), time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── 파서 ──────────────────────────────────────────────────────────────────────

def _extract_js_array(script: str, key: str) -> list[str] | None:
    """key:[...] 패턴에서 raw 원소 리스트 반환."""
    m = re.search(rf'{re.escape(key)}:\[([^\]]*)\]', script)
    if not m:
        return None
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def _parse_num(s: str) -> Optional[float]:
    s = s.strip().strip('"\'')
    if not s or s in ("null", "-", "N/A", "—") or "[PRO]" in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_script(html: str) -> tuple[list[dict], list[dict], Optional[str]]:
    """script 블록 → (revenue_rows, eps_rows, latest_date)."""
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    data_script = next((s for s in scripts if "table:{annual:{" in s), None)
    if not data_script:
        return [], [], None

    raw_dates    = _extract_js_array(data_script, "dates")
    raw_revenue  = _extract_js_array(data_script, "revenue")
    raw_eps      = _extract_js_array(data_script, "eps")
    raw_analysts = _extract_js_array(data_script, "analysts")

    if not raw_dates or not raw_revenue or not raw_eps:
        return [], [], None

    revenue_rows: list[dict] = []
    eps_rows: list[dict] = []

    for i, date_str in enumerate(raw_dates):
        year = date_str.strip('"\'')[:4]
        if not year.isdigit():
            continue

        # analysts[i] != "null" → 예상치
        analyst_val = raw_analysts[i] if raw_analysts and i < len(raw_analysts) else "null"
        is_estimate = analyst_val.strip() != "null"

        if i < len(raw_revenue):
            rev = _parse_num(raw_revenue[i])
            if rev is not None:
                revenue_rows.append({
                    "year": year,
                    "period_end": year,
                    "value": round(rev / 1_000_000, 0),  # 절대달러 → 백만달러
                    "is_estimate": is_estimate,
                })

        if i < len(raw_eps):
            eps = _parse_num(raw_eps[i])
            if eps is not None:
                eps_rows.append({
                    "year": year,
                    "period_end": year,
                    "value": eps,
                    "is_estimate": is_estimate,
                })

    # 최근 실적 발표일 — HTML에서 "Month DD, YYYY" 패턴으로 찾기
    latest_date: Optional[str] = None
    tree = HTMLParser(html)
    months = {"January":"01","February":"02","March":"03","April":"04","May":"05",
              "June":"06","July":"07","August":"08","September":"09",
              "October":"10","November":"11","December":"12"}
    for el in tree.css("td, span, div"):
        m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})$",
                     el.text(strip=True))
        if m:
            latest_date = f"{m.group(3)}.{months[m.group(1)]}.{m.group(2).zfill(2)}"
            break

    return revenue_rows, eps_rows, latest_date


def _fetch_roe_annual(ticker: str) -> list[dict]:
    """Net Income ÷ Shareholders' Equity → 연간 ROE(%).

    IS 페이지: fiscalYear + netIncome 배열
    BS 페이지: fiscalYear + equity 배열
    두 페이지 모두 fiscalYear:[년도 내림차순,...] 구조.
    파싱 실패 시 [] 반환.
    """
    base = f"https://stockanalysis.com/stocks/{ticker.lower()}"
    try:
        resp_is = _CLIENT.get(f"{base}/financials/")
        resp_is.raise_for_status()
        resp_bs = _CLIENT.get(f"{base}/financials/balance-sheet/")
        resp_bs.raise_for_status()
    except Exception as e:
        log.debug("ROE HTTP 실패 (%s): %s", ticker, e)
        return []

    def _extract_with_fiscal_year(html: str, key: str) -> dict[str, float]:
        """fiscalYear:[...] + key:[...] 패턴으로 연도별 값 추출."""
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        for s in scripts:
            m_years = re.search(r'fiscalYear:\[([^\]]*)\]', s)
            raw_vals = _extract_js_array(s, key)
            if not m_years or not raw_vals:
                continue
            years = [x.strip().strip('"\'') for x in m_years.group(1).split(",") if x.strip()]
            result = {}
            for i, year in enumerate(years):
                if not year.isdigit() or i >= len(raw_vals):
                    continue
                v = _parse_num(raw_vals[i])
                if v is not None:
                    result[year] = v
            if result:
                return result
        return {}

    net_income = _extract_with_fiscal_year(resp_is.text, "netIncome")
    equity = _extract_with_fiscal_year(resp_bs.text, "equity")

    if not net_income or not equity:
        return []

    result = []
    for year, ni in sorted(net_income.items()):
        eq = equity.get(year)
        if eq is None or eq == 0:
            continue
        result.append({
            "year": year,
            "period_end": year,
            "value": round(ni / eq * 100, 2),
            "is_estimate": False,
        })
    return result


# ── 공개 API ──────────────────────────────────────────────────────────────────

def fetch_annual_financials(ticker: str) -> Optional[dict]:
    """연간 재무 데이터 반환. 국내 종목은 None. 캐시 우선(24h TTL).

    Returns: {
        "revenue":  [{"year", "period_end", "value", "is_estimate"}, ...],
        "eps":      [...],
        "roe":      [...],
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

    revenue, eps, latest_date = _parse_script(resp.text)
    roe = _fetch_roe_annual(ticker)

    data: dict = {
        "revenue": revenue,
        "eps": eps,
        "roe": roe,
        "latest_report_date": latest_date,
    }
    # 빈 결과는 캐싱하지 않음 — 스크래핑 실패를 24h 동안 숨기는 것 방지
    if revenue or eps:
        _to_cache(ticker, data)
    return data
