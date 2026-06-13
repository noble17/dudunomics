"""관심종목/보유종목 펀더멘털 snapshot 명시 적재."""
from __future__ import annotations

import dataclasses
from datetime import date

import core.repository as repo
from core.data.fundamentals_scraper import FundamentalsSnapshot, fetch_fundamentals
from core.data.stockanalysis_financials import compute_consensus_growth
from core.ids import is_domestic

_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")


def hydrate_fundamental_snapshots(tickers: list[str] | None = None) -> dict:
    candidates = _normalize_candidates(tickers or repo.list_fundamental_hydration_tickers())
    result = {"requested": len(candidates), "updated": 0, "skipped": 0, "errors": []}

    for ticker in candidates:
        try:
            snapshot = fetch_fundamentals(ticker)
            if not snapshot:
                result["skipped"] += 1
                result["errors"].append(f"{ticker}: fundamentals 없음")
                continue
            repo.upsert_fundamental_snapshot(_snapshot_row(snapshot))
            result["updated"] += 1
        except Exception as exc:
            result["skipped"] += 1
            result["errors"].append(f"{ticker}: {type(exc).__name__}")

    return result


def _normalize_candidates(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if _skip_ticker(normalized):
            continue
        result.append(normalized)
    return result


def _skip_ticker(ticker: str) -> bool:
    return is_domestic(ticker) or ticker.endswith(_SKIP_SUFFIXES)


def _snapshot_row(snapshot: FundamentalsSnapshot) -> dict:
    growth = compute_consensus_growth(snapshot.ticker)
    raw = dataclasses.asdict(snapshot)
    return {
        "ticker": snapshot.ticker,
        "as_of": date.today(),
        "source": "finviz_stockanalysis",
        "per": snapshot.trailing_pe,
        "pbr": snapshot.price_to_book,
        "psr": snapshot.price_to_sales,
        "peg": snapshot.peg,
        "forward_pe": snapshot.forward_pe,
        "trailing_pe": snapshot.trailing_pe,
        "forward_eps": snapshot.forward_eps,
        "eps_ttm": snapshot.trailing_eps,
        "roe": snapshot.return_on_equity,
        "roic": snapshot.roic,
        "debt_ratio": snapshot.debt_to_equity,
        "current_ratio": snapshot.current_ratio,
        "gross_margin": snapshot.gross_margin,
        "operating_margin": snapshot.operating_margin,
        "revenue_growth": growth.get("rev_fwd_cagr"),
        "eps_growth": growth.get("eps_fwd_cagr"),
        "market_cap": snapshot.market_cap_m,
        "raw_json": {**raw, "growth": growth},
    }
