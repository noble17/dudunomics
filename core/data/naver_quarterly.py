"""core/data/naver_quarterly.py — 네이버 금융 분기 재무 스크래퍼 (KS/KQ 전용).

엔드포인트: https://m.stock.naver.com/api/stock/{code}/finance/quarter
isConsensus=Y 분기 제외. period 변환: '202503' → '2025Q1'
"""
from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}


def _yyyymm_to_period(yyyymm: str) -> str:
    year = yyyymm[:4]
    month = int(yyyymm[4:6])
    quarter = (month - 1) // 3 + 1
    return f"{year}Q{quarter}"


def _parse_float(value: str) -> float | None:
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_naver_quarterly(ticker: str) -> list[dict]:
    """네이버 분기 재무 반환. KS/KQ 아닌 티커는 빈 리스트."""
    upper = ticker.upper()
    if not (upper.endswith(".KS") or upper.endswith(".KQ")):
        return []
    code = upper[:-3]
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{code}/finance/quarter",
            headers=_HEADERS, timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        log.debug("naver quarterly 실패 (%s): %s", ticker, e)
        return []

    finance_info = data.get("financeInfo", {})
    title_list = finance_info.get("trTitleList", [])
    row_list = finance_info.get("rowList", [])
    confirmed_keys = [t["key"] for t in title_list if t.get("isConsensus") == "N"]

    def _col(row_title: str) -> dict:
        for row in row_list:
            if row.get("title") == row_title:
                return row.get("columns", {})
        return {}

    eps_cols   = _col("EPS")
    roe_cols   = _col("ROE")
    debt_cols  = _col("부채비율")
    rev_cols   = _col("매출액")
    opinc_cols = _col("영업이익")

    results = []
    for key in confirmed_keys:
        results.append({
            "ticker":     ticker,
            "period":     _yyyymm_to_period(key),
            "eps":        _parse_float(eps_cols.get(key, {}).get("value", "-")),
            "roe":        _parse_float(roe_cols.get(key, {}).get("value", "-")),
            "debt_ratio": _parse_float(debt_cols.get(key, {}).get("value", "-")),
            "revenue":    _parse_float(rev_cols.get(key, {}).get("value", "-")),
            "op_income":  _parse_float(opinc_cols.get(key, {}).get("value", "-")),
            "source":     "naver",
        })
    return sorted(results, key=lambda x: x["period"], reverse=True)
