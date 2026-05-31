# core/data/naver_fundamentals.py
"""네이버 금융 itemSummary API — 국내 종목 PER/PBR/EPS.

엔드포인트: https://api.finance.naver.com/service/itemSummary.naver?itemcode={code}
인증 불필요. Referer 헤더 필수.
"""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

_TTL = 600.0  # 10분
_cache: dict[str, tuple[dict, float]] = {}
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


def fetch_naver_summary(ticker: str) -> dict | None:
    """네이버 itemSummary에서 per/pbr/eps 반환.

    Args:
        ticker: 종목 티커 (예: '005930.KS', '035720.KQ')

    Returns:
        {"per": float|None, "pbr": float|None, "eps": float|None} or None
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

        result: dict = {
            "per": _safe(raw.get("per")),
            "pbr": _safe(raw.get("pbr")),
            "eps": _safe(raw.get("eps")),
        }
        _cache[code] = (result, now + _TTL)
        return result
    except Exception as e:
        log.debug("naver_fundamentals 실패 (%s): %s", ticker, e)
        return None
