"""Forward fundamentals 스냅샷 페치.

1차: fundamentals_scraper (Finviz + StockAnalysis) → 2차(fallback): yfinance
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from core.data.fundamentals_scraper import fetch_fundamentals as _scrape
from core.data.yf_session import get_session


def _safe_float(info: dict, key: str) -> float | None:
    v = info.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f  # NaN → None
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class FundamentalSnapshot:
    ticker: str
    as_of: date
    forward_eps: float | None
    forward_pe: float | None
    trailing_pe: float | None
    raw_json: str = field(default="{}", hash=False, compare=False)
    error: str | None = None


def _fetch_one(ticker: str, as_of: date) -> FundamentalSnapshot:
    # 1차: scraper (Finviz + StockAnalysis)
    scraped = _scrape(ticker)
    if scraped is not None:
        return FundamentalSnapshot(
            ticker=ticker,
            as_of=as_of,
            forward_eps=scraped.forward_eps,
            forward_pe=scraped.forward_pe,
            trailing_pe=scraped.trailing_pe,
            raw_json=json.dumps({
                "forwardEps": scraped.forward_eps,
                "forwardPE": scraped.forward_pe,
                "trailingPE": scraped.trailing_pe,
            }),
        )

    # 최후 fallback: yfinance
    import yfinance as yf
    try:
        info = yf.Ticker(ticker, session=get_session()).info
        return FundamentalSnapshot(
            ticker=ticker,
            as_of=as_of,
            forward_eps=_safe_float(info, "forwardEps"),
            forward_pe=_safe_float(info, "forwardPE"),
            trailing_pe=_safe_float(info, "trailingPE"),
            raw_json=json.dumps({
                "forwardEps": info.get("forwardEps"),
                "forwardPE": info.get("forwardPE"),
                "trailingPE": info.get("trailingPE"),
            }),
        )
    except Exception as e:
        return FundamentalSnapshot(
            ticker=ticker,
            as_of=as_of,
            forward_eps=None,
            forward_pe=None,
            trailing_pe=None,
            error=str(e),
        )


def fetch_snapshots(tickers: list[str], max_workers: int = 1) -> list[FundamentalSnapshot]:
    """순차 페치 (rate limiter 세션이 자체적으로 간격 조절).

    max_workers 파라미터는 하위 호환성을 위해 유지하나 사용되지 않음.
    병렬 yfinance 호출은 Yahoo IP 차단을 유발하므로 순차 실행.
    """
    from datetime import date as dt_date
    today = dt_date.today()

    if not tickers:
        return []

    results: list[FundamentalSnapshot] = []
    for ticker in tickers:
        results.append(_fetch_one(ticker, today))
    return results
