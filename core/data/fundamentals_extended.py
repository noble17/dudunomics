"""확장 펀더멘탈 스냅샷 — PBR, PSR, ROE, D/E Ratio, CFO, EPS TTM 페치.

1차: fundamentals_scraper (Finviz + StockAnalysis) → 2차(fallback): yfinance Ticker.info
병렬 페치로 500개 종목 처리 시간 최소화.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from core.data.fundamentals_scraper import fetch_fundamentals as _scrape

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
    # 국내 종목(.KS/.KQ)은 fundamentals 커버리지 없음 → 즉시 빈 스냅샷
    t_upper = ticker.upper()
    if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):
        return ExtendedSnapshot(ticker=ticker, as_of=as_of)

    # 1차: scraper (Finviz + StockAnalysis)
    scraped = _scrape(ticker)
    if scraped is not None:
        return ExtendedSnapshot(
            ticker=ticker,
            as_of=as_of,
            company_name=scraped.short_name or ticker,
            forward_pe=scraped.forward_pe,
            trailing_pe=scraped.trailing_pe,
            pbr=scraped.price_to_book,
            psr=scraped.price_to_sales,
            forward_eps=scraped.forward_eps,
            eps_ttm=scraped.trailing_eps,
            roe=scraped.return_on_equity,
            debt_to_equity=scraped.debt_to_equity,
            operating_cashflow=scraped.operating_cashflow,
        )

    # 최후 fallback: yfinance
    import yfinance as yf
    from core.data.yf_session import get_session
    try:
        info = yf.Ticker(ticker, session=get_session()).info
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


def fetch_extended(tickers: list[str], max_workers: int = 1) -> list[ExtendedSnapshot]:
    """순차 페치 (rate limiter 세션이 자체적으로 간격 조절).

    max_workers=1 고정 — yfinance 병렬 호출은 Yahoo IP 차단을 유발함.
    세션의 1 req/1.5s 레이트 리미터가 속도 제어.
    """
    from datetime import date as dt_date
    today = dt_date.today()
    results: list[ExtendedSnapshot] = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 0:
            log.info("[fundamentals] %d/%d 완료", i, total)
        results.append(_fetch_one(ticker, today))
    return results
