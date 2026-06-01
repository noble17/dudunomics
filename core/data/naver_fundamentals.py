# core/data/naver_fundamentals.py
"""네이버 금융 — 국내 종목 PER/PBR/EPS + 종목명 + 업종.

엔드포인트:
  - https://api.finance.naver.com/service/itemSummary.naver?itemcode={code} → PER/PBR/EPS
  - https://m.stock.naver.com/api/stock/{code}/integration → 종목명, 업종코드
  - https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no={n} → 업종명
인증 불필요. Referer 헤더 필수.
"""
from __future__ import annotations

import logging
import re
import time

import requests

log = logging.getLogger(__name__)

_TTL = 600.0  # 10분
_cache: dict[str, tuple[dict, float]] = {}
_industry_name_cache: dict[int, str] = {}  # 업종명 영구 캐시
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def _ticker_to_code(ticker: str) -> str | None:
    """'005930.KS' → '005930', '035720.KQ' → '035720'. 국내 종목이 아니면 None."""
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return upper[:-3]
    return None


def _fetch_industry_name(industry_code: int) -> str | None:
    """네이버 업종 페이지 title에서 업종명 파싱. 영구 캐시."""
    if industry_code in _industry_name_cache:
        return _industry_name_cache[industry_code]
    try:
        r = requests.get(
            "https://finance.naver.com/sise/sise_group_detail.naver",
            params={"type": "upjong", "no": industry_code},
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        m = re.search(r"<title>(.*?)</title>", r.text, re.IGNORECASE)
        if m:
            name = m.group(1).split(" :")[0].strip()
            if name:
                _industry_name_cache[industry_code] = name
                return name
    except Exception as e:
        log.debug("업종명 조회 실패 (%s): %s", industry_code, e)
    return None


def _fetch_stock_info(code: str) -> tuple[str | None, str | None, float | None, float | None]:
    """네이버 integration API → (종목명, 업종명, 추정PER, 추정EPS). 실패 시 모두 None."""
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{code}/integration",
            headers=_HEADERS,
            timeout=8,
        )
        if r.status_code != 200:
            return None, None, None, None
        d = r.json()
        stock_name: str | None = d.get("stockName")
        industry_code = d.get("industryCode")
        sector = _fetch_industry_name(int(industry_code)) if industry_code else None

        cns_per: float | None = None
        cns_eps: float | None = None
        for item in d.get("totalInfos", []):
            code_key = item.get("code")
            raw_val = item.get("value", "")
            try:
                cleaned = raw_val.replace(",", "").replace("배", "").replace("원", "").strip()
                val = float(cleaned) if cleaned else None
            except (ValueError, TypeError):
                val = None
            if code_key == "cnsPer":
                cns_per = val if val and val > 0 else None
            elif code_key == "cnsEps":
                cns_eps = val if val and val > 0 else None

        return stock_name, sector, cns_per, cns_eps
    except Exception as e:
        log.debug("naver stock info 실패 (%s): %s", code, e)
        return None, None, None, None


def fetch_naver_summary(ticker: str) -> dict | None:
    """네이버 itemSummary에서 per/pbr/eps 반환.

    Args:
        ticker: 종목 티커 (예: '005930.KS', '035720.KQ')

    Returns:
        {"per": float|None, "pbr": float|None, "eps": float|None,
         "name": str|None, "sector": str|None} or None
        - 국내 종목이 아니면 None
        - 네트워크 오류 시 None
        - per/pbr/eps가 0이면 None으로 변환 (데이터 없음 의미)
    """
    code = _ticker_to_code(ticker)
    if not code:
        return None

    now = time.time()
    if code in _cache:
        data, exp = _cache[code]
        if now < exp:
            return data

    try:
        r = requests.get(
            "https://api.finance.naver.com/service/itemSummary.naver",
            params={"itemcode": code},
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        raw = r.json()

        def _safe(val: object) -> float | None:
            if val is None or val == 0:
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        stock_name, sector, cns_per, cns_eps = _fetch_stock_info(code)
        result: dict = {
            "per": _safe(raw.get("per")),
            "pbr": _safe(raw.get("pbr")),
            "eps": _safe(raw.get("eps")),
            "fwd_per": cns_per,
            "fwd_eps": cns_eps,
            "name": stock_name,
            "sector": sector,
        }
        _cache[code] = (result, now + _TTL)
        return result
    except Exception as e:
        log.debug("naver_fundamentals 실패 (%s): %s", ticker, e)
        return None
