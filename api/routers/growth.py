"""성장주 탐색 엔드포인트."""
from __future__ import annotations

import json
import logging
import math
from datetime import date, timedelta
from typing import Literal

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.models import GrowthHydrateOut, GrowthScoreOut, GrowthTimingOut, GrowthValuationOut, GrowthWatchlistStatusOut
from core.auth.deps import CurrentUser, current_user
from core.data.normalization import normalize_finite_numbers
from core.data.ohlcv_cache import fetch_ohlcv
from core.data.fundamentals_scraper import fetch_fundamentals
from core.data.price_target_consensus import fetch_price_target_consensus
from core.data.stockanalysis_financials import compute_consensus_growth
from core.data.ticker_data_service import get_fundamentals
from core.prices.kis import KISPriceProvider
from core.scoring.growth_scorer import filter_growth_top
from core.scoring.technical_timing import analyze_timing
import core.repository as repo


router = APIRouter(prefix="/api/growth", tags=["growth"])
log = logging.getLogger(__name__)
_price_provider = KISPriceProvider()
_KR_UNIVERSES = {"kospi200", "kosdaq150"}


@router.get("/scores", response_model=list[GrowthScoreOut])
def get_scores(universe: str = "sp500", user: CurrentUser = Depends(current_user)):
    rows = _latest_rows(universe)
    return _with_rank_deltas(rows, universe)


@router.get("/top", response_model=list[GrowthScoreOut])
def get_top(
    universe: str = "sp500",
    sector: str | None = None,
    cap: str | None = None,
    signal: Literal["all", "aligned", "pullback", "volume", "suitable"] = "all",
    limit: int = 10,
    user: CurrentUser = Depends(current_user),
):
    rows = _latest_rows(universe)
    frame = pd.DataFrame([_to_filter_row(row) for row in rows]).set_index("ticker")
    top = filter_growth_top(
        frame,
        market="KR" if universe in _KR_UNIVERSES else "US",
        sector=sector,
        cap=cap,
        limit=limit,
    )
    wanted = set(top.index)
    candidates = [row for row in _with_rank_deltas(rows, universe) if row["ticker"] in wanted]
    return _with_timing(candidates, signal)


@router.get("/watchlist", response_model=list[GrowthScoreOut])
def get_watchlist(universe: str = "sp500", user: CurrentUser = Depends(current_user)):
    watchlist_id = repo.ensure_default_watchlist(user.id)
    tickers = {
        item["ticker"]
        for item in repo.list_watchlist_items(user.id, watchlist_id)
        if item["universe"] == universe
    }
    if not tickers:
        return []
    rows = _latest_rows(universe)
    candidates = [row for row in _with_rank_deltas(rows, universe) if row["ticker"] in tickers]
    return _with_timing(candidates, "all")


@router.get("/watchlist/{ticker}", response_model=GrowthWatchlistStatusOut)
def get_watchlist_status(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    watchlist_id = repo.ensure_default_watchlist(user.id)
    tickers = {
        item["ticker"]
        for item in repo.list_watchlist_items(user.id, watchlist_id)
        if item["universe"] == universe
    }
    return {
        "ticker": ticker,
        "universe": universe,
        "in_watchlist": ticker in tickers,
    }


@router.put("/watchlist/{ticker}", response_model=GrowthWatchlistStatusOut)
def add_watchlist_item(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    watchlist_id = repo.ensure_default_watchlist(user.id)
    name = None
    row = repo.get_quant_ticker(ticker, universe)
    if row:
        name = row.get("company_name")
    repo.upsert_watchlist_item(user.id, watchlist_id, ticker, universe, name=name)
    return {"ticker": ticker, "universe": universe, "in_watchlist": True}


@router.delete("/watchlist/{ticker}", response_model=GrowthWatchlistStatusOut)
def remove_watchlist_item(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    watchlist_id = repo.ensure_default_watchlist(user.id)
    repo.remove_watchlist_item(user.id, watchlist_id, ticker, universe)
    return {"ticker": ticker, "universe": universe, "in_watchlist": False}


@router.get("/ticker/{ticker}/valuation", response_model=GrowthValuationOut)
def get_valuation(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    row = repo.get_quant_ticker(ticker, universe)
    common = get_fundamentals(ticker, universe=universe)
    has_common_snapshot = row is None and common.get("valuation_source") is not None
    fallback = None if row or has_common_snapshot else _on_demand_valuation(ticker)
    try:
        consensus = fetch_price_target_consensus(ticker)
    except Exception as exc:
        log.warning(
            "price target consensus fetch failed ticker=%s source=%s error_type=%s",
            ticker,
            _consensus_source(ticker),
            type(exc).__name__,
        )
        consensus = _temporary_consensus_error(ticker)
    consensus = _with_current_price(ticker, consensus)
    return normalize_finite_numbers({
        "ticker": ticker,
        **_score_status(ticker, universe, row),
        "valuation_source": "BATCH" if row else common["valuation_source"] if has_common_snapshot else fallback["valuation_source"],
        "missing_reasons": [] if row or has_common_snapshot else fallback["missing_reasons"],
        "peg": row.get("raw_peg") if row else common["peg"] if has_common_snapshot else fallback["peg"],
        "forward_pe": row.get("raw_fwd_pe") if row else common["forward_pe"] if has_common_snapshot else fallback["forward_pe"],
        "psr": row.get("raw_psr") if row else common["psr"] if has_common_snapshot else fallback["psr"],
        "forward_eps": row.get("raw_fwd_eps") if row else common["forward_eps"] if has_common_snapshot else fallback["forward_eps"],
        "forward_revenue_growth": row.get("raw_fwd_rev_growth") if row else common["forward_revenue_growth"] if has_common_snapshot else fallback["forward_revenue_growth"],
        "forward_eps_growth": row.get("raw_fwd_eps_growth") if row else common["forward_eps_growth"] if has_common_snapshot else fallback["forward_eps_growth"],
        **consensus,
    })


@router.get("/ticker/{ticker}/timing", response_model=GrowthTimingOut)
def get_timing(ticker: str, user: CurrentUser = Depends(current_user)):
    ticker = ticker.upper()
    try:
        timing = analyze_timing(ticker)
    except Exception as exc:
        log.warning("timing analysis failed ticker=%s error_type=%s", ticker, type(exc).__name__)
        timing = {
            "status": "unknown",
            "reason": "타이밍 분석 중 일시적인 오류가 발생했습니다.",
        }
    return normalize_finite_numbers(timing)


@router.post("/ticker/{ticker}/hydrate", response_model=GrowthHydrateOut)
def hydrate_ticker(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    today = date.today()
    _, warnings = fetch_ohlcv([ticker], today - timedelta(days=420), today, force=True)
    timing = analyze_timing(ticker)
    return normalize_finite_numbers({
        "ticker": ticker,
        "universe": universe,
        "warnings": warnings,
        "timing_status": timing.get("status"),
        "timing_rows": timing.get("rows"),
        "volume_level": timing.get("volume_level"),
        "volume_direction": timing.get("volume_direction"),
        "rsi14": timing.get("rsi14"),
        "rsi_level": timing.get("rsi_level"),
        "positive_reasons": timing.get("positive_reasons") or [],
        "warning_reasons": timing.get("warning_reasons") or [],
        "downgrade_reasons": timing.get("downgrade_reasons") or [],
    })


@router.post("/refresh")
def refresh(
    universe: str = "sp500",
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    user: CurrentUser = Depends(current_user),
):
    from core.batch_refresh import (
        BatchAlreadyRunningError,
        DartApiKeyRequiredError,
        refresh as refresh_batch,
    )

    try:
        return refresh_batch(universe, background_tasks=background_tasks, force=force)
    except BatchAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DartApiKeyRequiredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _latest_rows(universe: str) -> list[dict]:
    rows = repo.get_latest_quant_scores(universe)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"유니버스 '{universe}' 데이터 없음. /api/growth/refresh 먼저 실행 필요.",
        )
    return rows


def _with_rank_deltas(rows: list[dict], universe: str) -> list[dict]:
    deltas = repo.get_rank_deltas(universe, rows[0]["as_of"])
    enriched = [
        {
            **row,
            "data_coverage": _decode_coverage(row.get("data_coverage")),
            **deltas.get(row["ticker"], {}),
        }
        for row in rows
    ]
    return normalize_finite_numbers(
        sorted(enriched, key=lambda row: row.get("growth_composite") or -1, reverse=True)
    )


def _to_filter_row(row: dict) -> dict:
    return {
        "ticker": row["ticker"],
        "sector": row.get("sector"),
        "growth_composite": row.get("growth_composite"),
        "debt_to_equity": row.get("raw_debt_ratio"),
        "fcf_yield": row.get("raw_fcf_yield"),
        "operating_cashflow": row.get("raw_operating_cashflow"),
        "current_ratio": row.get("raw_current_ratio"),
        "operating_margin": row.get("raw_oper_margin"),
        "roe": _percent_to_decimal(row.get("raw_roe")),
        "roic": row.get("raw_roic"),
        "market_cap_usd_m": row.get("raw_market_cap_usd_m"),
        "market_cap_krw": row.get("raw_market_cap_krw"),
    }


def _with_timing(rows: list[dict], signal: str) -> list[dict]:
    enriched = []
    for row in rows:
        try:
            timing = analyze_timing(row["ticker"])
        except Exception as exc:
            log.warning(
                "timing analysis failed ticker=%s error_type=%s",
                row["ticker"],
                type(exc).__name__,
            )
            timing = {"status": "unknown"}
        if signal != "all" and not _matches_signal(timing, signal):
            continue
        enriched.append({
            **row,
            "timing_status": timing.get("status"),
            "timing_aligned": timing.get("aligned"),
            "timing_pullback": timing.get("pullback"),
            "timing_pullback_stage": timing.get("pullback_stage"),
            "timing_volume_explosion": timing.get("volume_explosion"),
            "timing_volume_level": timing.get("volume_level"),
            "timing_volume_direction": timing.get("volume_direction"),
            "timing_rsi_level": timing.get("rsi_level"),
            "timing_downgrade_reasons": timing.get("downgrade_reasons") or [],
        })
    return enriched


def _temporary_consensus_error(ticker: str) -> dict:
    return {
        "consensus_status": "temporary_error",
        "consensus_message": "목표주가 조회 중 일시적인 오류가 발생했습니다.",
        "consensus_source": _consensus_source(ticker),
        "retry_after": None,
        "current_price": None,
        "target_mean": None,
        "target_median": None,
        "target_low": None,
        "target_high": None,
        "upside_pct": None,
        "analyst_count": None,
        "consensus_as_of": None,
    }


def _score_status(ticker: str, universe: str, row: dict | None) -> dict:
    if row:
        return {
            "score_status": "ok",
            "score_message": None,
        }
    return {
        "score_status": "missing",
        "score_message": f"{ticker}는 {universe} 성장주 배치 데이터에 아직 없습니다.",
    }


def _on_demand_valuation(ticker: str) -> dict:
    snap = fetch_fundamentals(ticker)
    growth = compute_consensus_growth(ticker)
    if not snap:
        return {
            "valuation_source": None,
            "missing_reasons": _on_demand_missing_reasons(None, growth),
            "peg": None,
            "forward_pe": None,
            "psr": None,
            "forward_eps": None,
            "forward_revenue_growth": growth.get("rev_fwd_cagr"),
            "forward_eps_growth": growth.get("eps_fwd_cagr"),
        }
    missing = []
    values = {
        "peg": snap.peg,
        "forward_pe": snap.forward_pe,
        "psr": snap.price_to_sales,
        "forward_eps": snap.forward_eps,
    }
    if all(value is None for value in values.values()):
        missing.append("Finviz valuation 지표 미제공")
    if growth.get("rev_fwd_cagr") is None:
        missing.append("StockAnalysis 매출 CAGR 미제공")
    if growth.get("eps_fwd_cagr") is None:
        missing.append("StockAnalysis EPS CAGR 미제공")
    return {
        "valuation_source": "FINVIZ",
        "missing_reasons": missing,
        "forward_revenue_growth": growth.get("rev_fwd_cagr"),
        "forward_eps_growth": growth.get("eps_fwd_cagr"),
        **values,
    }


def _on_demand_missing_reasons(snap, growth: dict) -> list[str]:
    reasons = []
    if not snap:
        reasons.append("Finviz fundamentals 미제공")
    if growth.get("rev_fwd_cagr") is None:
        reasons.append("StockAnalysis 매출 CAGR 미제공")
    if growth.get("eps_fwd_cagr") is None:
        reasons.append("StockAnalysis EPS CAGR 미제공")
    return reasons


def _with_current_price(ticker: str, consensus: dict) -> dict:
    try:
        current_price = float(_price_provider.get_current_price(ticker).current)
    except Exception as exc:
        log.warning("live price fetch failed ticker=%s error_type=%s", ticker, type(exc).__name__)
        return consensus
    if not _is_positive_finite(current_price):
        return consensus
    updated = {**consensus, "current_price": current_price}
    target_mean = consensus.get("target_mean")
    if _is_positive_finite(target_mean):
        updated["upside_pct"] = (float(target_mean) - current_price) / current_price * 100
    return updated


def _is_positive_finite(value) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _consensus_source(ticker: str) -> str:
    return "KIS" if ticker.endswith((".KS", ".KQ")) else "FMP"


def _matches_signal(timing: dict, signal: str) -> bool:
    if signal == "aligned":
        return timing.get("aligned") is True
    if signal == "pullback":
        return timing.get("aligned") is True and timing.get("pullback") is True
    if signal == "volume":
        return (
            timing.get("aligned") is True
            and timing.get("volume_direction") == "bullish"
            and (timing.get("volume_ratio") or 0) >= 1.0
        )
    if signal == "suitable":
        return timing.get("status") == "suitable"
    return True


def _decode_coverage(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _percent_to_decimal(value):
    return value / 100.0 if value is not None else None
