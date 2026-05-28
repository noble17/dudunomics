"""확장 펀더멘탈 스냅샷 — PBR, PSR, ROE, D/E Ratio, CFO, EPS TTM 페치.

yfinance Ticker.info 딕셔너리에서 필드 추출.
병렬 페치로 500개 종목 처리 시간 최소화.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtendedSnapshot:
    ticker: str
    as_of: date
    company_name: str | None = None
    # 밸류에이션
    forward_pe: float | None = None
    trailing_pe: float | None = None
    pbr: float | None = None       # priceToBook
    psr: float | None = None       # priceToSalesTrailing12Months
    # 어닝스
    forward_eps: float | None = None
    eps_ttm: float | None = None   # trailingEps
    # 퀄리티
    roe: float | None = None               # returnOnEquity
    debt_to_equity: float | None = None    # debtToEquity (단위: %, 예: 150 = 1.5배)
    operating_cashflow: float | None = None  # operatingCashflow
    error: str | None = field(default=None, hash=False, compare=False)


def _safe(info: dict, key: str) -> float | None:
    v = info.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f  # NaN guard
    except (ValueError, TypeError):
        return None


def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        return ExtendedSnapshot(
            ticker=ticker,
            as_of=as_of,
            company_name=info.get("shortName") or info.get("longName"),
            forward_pe=_safe(info, "forwardPE"),
            trailing_pe=_safe(info, "trailingPE"),
            pbr=_safe(info, "priceToBook"),
            psr=_safe(info, "priceToSalesTrailing12Months"),
            forward_eps=_safe(info, "forwardEps"),
            eps_ttm=_safe(info, "trailingEps"),
            roe=_safe(info, "returnOnEquity"),
            debt_to_equity=_safe(info, "debtToEquity"),
            operating_cashflow=_safe(info, "operatingCashflow"),
        )
    except Exception as e:
        log.warning("ExtendedSnapshot 페치 실패 (%s): %s", ticker, e)
        return ExtendedSnapshot(ticker=ticker, as_of=as_of, error=str(e))


def fetch_extended(tickers: list[str], max_workers: int = 20) -> list[ExtendedSnapshot]:
    """ThreadPool으로 복수 티커 동시 페치."""
    from datetime import date as dt_date
    today = dt_date.today()
    results: list[ExtendedSnapshot] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(tickers))) as ex:
        futures = {ex.submit(_fetch_one, t, today): t for t in tickers}
        for future in as_completed(futures):
            results.append(future.result())
    return results
