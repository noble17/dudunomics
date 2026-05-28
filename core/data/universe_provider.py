"""S&P 500 유니버스 티커 목록 제공.

Wikipedia HTML 테이블 파싱으로 티커 취득 (yfinance 제공 없음).
네트워크 불가 시 캐시된 JSON 파일을 fallback으로 사용.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CACHE_PATH = Path("data/sp500_tickers.json")


def get_sp500_tickers() -> list[str]:
    """S&P 500 구성 종목 티커 반환. Wikipedia 파싱 → 캐시 파일 fallback."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(_WIKI_URL, headers=headers, timeout=10)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(tickers))
        log.info("S&P 500 티커 %d개 취득 (Wikipedia)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("Wikipedia 파싱 실패 (%s) — 캐시 파일 시도", e)
        if _CACHE_PATH.exists():
            tickers = json.loads(_CACHE_PATH.read_text())
            log.info("S&P 500 티커 %d개 취득 (캐시)", len(tickers))
            return tickers
        raise RuntimeError("S&P 500 티커 목록 취득 불가. 네트워크 확인 필요.") from e


UNIVERSE_PROVIDERS = {
    "sp500": get_sp500_tickers,
}


def get_tickers(universe: str) -> list[str]:
    provider = UNIVERSE_PROVIDERS.get(universe)
    if not provider:
        raise ValueError(f"Unknown universe: {universe}. 지원: {list(UNIVERSE_PROVIDERS)}")
    return provider()
