"""유니버스별 티커 목록 제공.

S&P 500   : Wikipedia HTML 파싱
Nasdaq 100: Wikipedia HTML 파싱
KOSPI 200 : FDR KRX 전체 목록 → KOSPI 시총 상위 200
KOSDAQ 150: FDR KRX 전체 목록 → KOSDAQ 시총 상위 150

네트워크 불가 시 data/ 하위 캐시 JSON fallback.
"""
from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)
_DATA = Path("data")
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _load_cache(path: Path) -> list[str] | None:
    if path.exists():
        tickers = json.loads(path.read_text())
        log.info("캐시에서 %d개 티커 로드: %s", len(tickers), path.name)
        return tickers
    return None


def _save_cache(path: Path, tickers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tickers))


# ── S&P 500 ──────────────────────────────────────────────────────────────────

def get_sp500_tickers() -> list[str]:
    cache = _DATA / "sp500_tickers.json"
    try:
        r = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=_HEADERS, timeout=10,
        )
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        _save_cache(cache, tickers)
        log.info("S&P 500 티커 %d개 취득 (Wikipedia)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("S&P 500 Wikipedia 실패 (%s) — 캐시 시도", e)
        cached = _load_cache(cache)
        if cached:
            return cached
        raise RuntimeError("S&P 500 티커 목록 취득 불가") from e


# ── Nasdaq 100 ────────────────────────────────────────────────────────────────

def get_nasdaq100_tickers() -> list[str]:
    cache = _DATA / "nasdaq100_tickers.json"
    try:
        r = requests.get(
            "https://en.wikipedia.org/wiki/Nasdaq-100",
            headers=_HEADERS, timeout=10,
        )
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        tickers: list[str] = []
        for t in tables:
            if "Ticker" in t.columns:
                tickers = t["Ticker"].dropna().tolist()
                break
        if not tickers:
            raise ValueError("Ticker 컬럼을 찾을 수 없음")
        _save_cache(cache, tickers)
        log.info("Nasdaq 100 티커 %d개 취득 (Wikipedia)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("Nasdaq 100 Wikipedia 실패 (%s) — 캐시 시도", e)
        cached = _load_cache(cache)
        if cached:
            return cached
        raise RuntimeError("Nasdaq 100 티커 목록 취득 불가") from e


# ── KOSPI 200 / KOSDAQ 150 ───────────────────────────────────────────────────

def _get_krx_listing() -> pd.DataFrame:
    """FDR KRX 전체 상장종목 (Code, Market, Marcap)."""
    import FinanceDataReader as fdr
    return fdr.StockListing("KRX")[["Code", "Market", "Marcap"]].dropna(subset=["Marcap"])


def get_kospi200_tickers() -> list[str]:
    cache = _DATA / "kospi200_tickers.json"
    try:
        df = _get_krx_listing()
        top = df[df["Market"] == "KOSPI"].nlargest(200, "Marcap")
        tickers = [f"{c}.KS" for c in top["Code"].tolist()]
        _save_cache(cache, tickers)
        log.info("KOSPI 200 티커 %d개 취득 (FDR 시총 상위 200)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("KOSPI 200 FDR 실패 (%s) — 캐시 시도", e)
        cached = _load_cache(cache)
        if cached:
            return cached
        raise RuntimeError("KOSPI 200 티커 목록 취득 불가") from e


def get_kosdaq150_tickers() -> list[str]:
    cache = _DATA / "kosdaq150_tickers.json"
    try:
        df = _get_krx_listing()
        top = df[df["Market"] == "KOSDAQ"].nlargest(150, "Marcap")
        tickers = [f"{c}.KQ" for c in top["Code"].tolist()]
        _save_cache(cache, tickers)
        log.info("KOSDAQ 150 티커 %d개 취득 (FDR 시총 상위 150)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("KOSDAQ 150 FDR 실패 (%s) — 캐시 시도", e)
        cached = _load_cache(cache)
        if cached:
            return cached
        raise RuntimeError("KOSDAQ 150 티커 목록 취득 불가") from e


# ── 라우터 ────────────────────────────────────────────────────────────────────

UNIVERSE_PROVIDERS = {
    "sp500":      get_sp500_tickers,
    "nasdaq100":  get_nasdaq100_tickers,
    "kospi200":   get_kospi200_tickers,
    "kosdaq150":  get_kosdaq150_tickers,
}

UNIVERSE_LABELS = {
    "sp500":     "S&P 500",
    "nasdaq100": "Nasdaq 100",
    "kospi200":  "KOSPI 200",
    "kosdaq150": "KOSDAQ 150",
}


def get_tickers(universe: str) -> list[str]:
    provider = UNIVERSE_PROVIDERS.get(universe)
    if not provider:
        raise ValueError(f"Unknown universe: {universe}. 지원: {list(UNIVERSE_PROVIDERS)}")
    return provider()
