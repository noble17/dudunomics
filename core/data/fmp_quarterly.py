"""core/data/fmp_quarterly.py — FMP API 분기 재무 스크래퍼 (US 전용).

엔드포인트:
  /v3/income-statement/{ticker}?period=quarter&limit=8
  /v3/financial-ratios/{ticker}?period=quarter&limit=8
FMP_API_KEY 환경변수 필요. KS/KQ 티커는 skip.
"""
from __future__ import annotations
import logging
import os
import requests

log = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")


def _cal_period(entry: dict) -> str:
    year = str(entry.get("calendarYear", ""))
    q = entry.get("period", "")
    if year and q:
        return f"{year}{q}"
    date_str = entry.get("date", "")
    if len(date_str) >= 7:
        year2 = date_str[:4]
        month = int(date_str[5:7])
        q2 = (month - 1) // 3 + 1
        return f"{year2}Q{q2}"
    return ""


def fetch_fmp_quarterly(ticker: str) -> list[dict]:
    """FMP 분기 재무 반환. KS/KQ는 빈 리스트. FMP_API_KEY 없으면 빈 리스트."""
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return []
    api_key = FMP_API_KEY
    if not api_key:
        log.warning("FMP_API_KEY 미설정 — quarterly 스킵")
        return []
    try:
        income_r = requests.get(f"{_BASE}/income-statement/{ticker}", params={"period": "quarter", "limit": 8, "apikey": api_key}, timeout=10)
        ratios_r = requests.get(f"{_BASE}/financial-ratios/{ticker}", params={"period": "quarter", "limit": 8, "apikey": api_key}, timeout=10)
    except Exception as e:
        log.debug("FMP quarterly 실패 (%s): %s", ticker, e)
        return []
    if income_r.status_code != 200 or ratios_r.status_code != 200:
        return []

    income_list = income_r.json()
    ratios_list = ratios_r.json()

    ratios_by_period: dict[str, dict] = {}
    for entry in (ratios_list if isinstance(ratios_list, list) else []):
        p = _cal_period(entry)
        if p:
            ratios_by_period[p] = entry

    results = []
    for entry in (income_list if isinstance(income_list, list) else []):
        period = _cal_period(entry)
        if not period:
            continue
        ratio = ratios_by_period.get(period, {})
        roe_raw = ratio.get("returnOnEquity")
        de_raw = ratio.get("debtEquityRatio")
        rev_raw = entry.get("revenue")
        results.append({
            "ticker":     ticker,
            "period":     period,
            "eps":        entry.get("eps"),
            "roe":        round(roe_raw * 100, 4) if roe_raw is not None else None,
            "debt_ratio": round(de_raw * 100, 4) if de_raw is not None else None,
            "revenue":    round(rev_raw / 1_000_000, 2) if rev_raw is not None else None,
            "op_income":  round(entry["operatingIncome"] / 1_000_000, 2) if entry.get("operatingIncome") is not None else None,
            "source":     "fmp",
        })
    return sorted(results, key=lambda x: x["period"], reverse=True)
