"""확장 펀더멘탈 스냅샷 — EV/EBITDA, FCF Yield, PEG, 섹터 포함.

1차: fundamentals_scraper (Finviz + StockAnalysis) → 실패 시 빈 스냅샷 반환.
yfinance 의존성 없음.
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
    pbr: float | None = None
    psr: float | None = None
    ev_ebitda: float | None = None
    peg: float | None = None
    market_cap_m: float | None = None
    # 현금흐름
    operating_cashflow: float | None = None
    capex: float | None = None
    fcf_yield: float | None = None
    # 어닝스
    forward_eps: float | None = None
    eps_ttm: float | None = None
    # 퀄리티
    roe: float | None = None
    debt_to_equity: float | None = None
    # 자본잠식
    negative_book_value: bool = False
    # 섹터
    sector: str | None = None
    industry: str | None = None
    error: str | None = field(default=None, hash=False, compare=False)


def _compute_fcf_yield(ocf: float | None, capex: float | None, market_cap_m: float | None) -> float | None:
    # ocf, capex은 달러 단위 / market_cap_m은 백만 달러 단위
    if ocf is None or capex is None or not market_cap_m or market_cap_m <= 0:
        return None
    return (ocf - capex) / (market_cap_m * 1_000_000)


def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    t_upper = ticker.upper()
    if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):
        from core.data.naver_fundamentals import fetch_naver_summary
        nav = fetch_naver_summary(ticker)
        if nav:
            return ExtendedSnapshot(
                ticker=ticker,
                as_of=as_of,
                company_name=nav.get("name"),
                forward_pe=nav.get("fwd_per"),
                trailing_pe=nav["per"],
                pbr=nav["pbr"],
                forward_eps=nav.get("fwd_eps"),
                eps_ttm=nav["eps"],
                sector=nav.get("sector"),
            )
        return ExtendedSnapshot(ticker=ticker, as_of=as_of)

    scraped = _scrape(ticker)
    if scraped is None:
        return ExtendedSnapshot(ticker=ticker, as_of=as_of, error="scrape_failed")

    return ExtendedSnapshot(
        ticker=ticker,
        as_of=as_of,
        company_name=scraped.short_name or ticker,
        forward_pe=scraped.forward_pe,
        trailing_pe=scraped.trailing_pe,
        pbr=scraped.price_to_book,
        psr=scraped.price_to_sales,
        ev_ebitda=scraped.ev_ebitda if (scraped.ev_ebitda is not None and scraped.ev_ebitda > 0) else None,
        peg=scraped.peg,
        market_cap_m=scraped.market_cap_m,
        operating_cashflow=scraped.operating_cashflow,
        capex=scraped.capex,
        fcf_yield=_compute_fcf_yield(scraped.operating_cashflow, scraped.capex, scraped.market_cap_m),
        forward_eps=scraped.forward_eps,
        eps_ttm=scraped.trailing_eps,
        roe=scraped.return_on_equity,
        debt_to_equity=scraped.debt_to_equity,
        negative_book_value=scraped.negative_book_value,
        sector=scraped.sector,
        industry=scraped.industry,
    )


def fetch_extended(
    tickers: list[str],
    max_workers: int = 1,
    progress_callback=None,
) -> list[ExtendedSnapshot]:
    """순차 페치. progress_callback(done, total): 각 티커 완료 후 호출."""
    from datetime import date as dt_date
    today = dt_date.today()
    results: list[ExtendedSnapshot] = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 0:
            log.info("[fundamentals] %d/%d 완료", i, total)
        results.append(_fetch_one(ticker, today))
        if progress_callback:
            progress_callback(i, total)
    return results
