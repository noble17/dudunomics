"""Forward fundamentals 스냅샷 페치 (yfinance)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date


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
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
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


def fetch_snapshots(tickers: list[str], max_workers: int = 8) -> list[FundamentalSnapshot]:
    """ThreadPool으로 복수 티커 fundamentals 동시 페치."""
    from datetime import date as dt_date
    today = dt_date.today()

    if not tickers:
        return []

    results: list[FundamentalSnapshot] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(tickers))) as executor:
        futures = {executor.submit(_fetch_one, t, today): t for t in tickers}
        for future in as_completed(futures):
            results.append(future.result())
    return results
