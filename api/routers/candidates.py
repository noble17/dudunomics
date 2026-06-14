"""후보 발굴 엔드포인트."""
from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.models import CandidateRefreshOut, CandidateScoreOut, CandidateShortlistIn
from core.auth.deps import CurrentUser, current_user
from core.candidates.scorer import decode_raw_json, refresh_candidate_scores
from core.data.choicestock_public import get_public_summary
import core.repository as repo


router = APIRouter(prefix="/api/candidates", tags=["candidates"])
log = logging.getLogger(__name__)


@router.get("", response_model=list[CandidateScoreOut])
def list_candidates(
    region: Literal["all", "US", "KR"] = "all",
    sector: Literal["all", "tech"] = "tech",
    status: Literal["new", "watching", "dismissed", "added", "all"] = "new",
    source: str = "all",
    limit: int = 50,
    exclude_watchlist: bool = True,
    growth_weight: float = 25,
    quality_weight: float = 20,
    valuation_weight: float = 15,
    momentum_weight: float = 20,
    timing_weight: float = 15,
    liquidity_weight: float = 5,
    min_growth_score: float | None = None,
    min_quality_score: float | None = None,
    min_valuation_score: float | None = None,
    min_momentum_score: float | None = None,
    min_timing_score: float | None = None,
    min_liquidity_score: float | None = None,
    min_market_cap: float | None = None,
    max_forward_pe: float | None = None,
    max_peg: float | None = None,
    min_roe: float | None = None,
    max_rsi: float | None = None,
    require_above_ma200: bool = False,
    positive_eps_growth: bool = False,
    positive_revenue_growth: bool = False,
    user: CurrentUser = Depends(current_user),
):
    rows = repo.get_latest_candidate_scores(None if region == "all" else region)
    shortlist = {
        (item["ticker"], item["universe_group"]): item
        for item in repo.list_candidate_shortlist(user.id)
    }
    watchlist_tickers = _watchlist_tickers(user.id)
    enriched = [_enrich(row, shortlist, watchlist_tickers) for row in rows]
    filtered = [
        row for row in enriched
        if _matches_sector(row, sector)
        and _matches_status(row, status)
        and _matches_source(row, source)
        and (not exclude_watchlist or not row.get("in_watchlist"))
        and _matches_numeric_filters(
            row,
            min_growth_score=min_growth_score,
            min_quality_score=min_quality_score,
            min_valuation_score=min_valuation_score,
            min_momentum_score=min_momentum_score,
            min_timing_score=min_timing_score,
            min_liquidity_score=min_liquidity_score,
            min_market_cap=min_market_cap,
            max_forward_pe=max_forward_pe,
            max_peg=max_peg,
            min_roe=min_roe,
            max_rsi=max_rsi,
            require_above_ma200=require_above_ma200,
            positive_eps_growth=positive_eps_growth,
            positive_revenue_growth=positive_revenue_growth,
        )
    ]
    filtered = _rerank_with_weights(filtered, {
        "growth_score": growth_weight,
        "quality_score": quality_weight,
        "valuation_score": valuation_weight,
        "momentum_score": momentum_weight,
        "timing_score": timing_weight,
        "liquidity_score": liquidity_weight,
    })
    return _limit_by_region(filtered, region, source, limit)


@router.post("/refresh", response_model=CandidateRefreshOut)
def refresh_candidates(
    region: Literal["all", "US", "KR"] = "all",
    user: CurrentUser = Depends(current_user),
):
    return refresh_candidate_scores(region)


@router.put("/{ticker}/shortlist", response_model=dict)
def update_shortlist(
    ticker: str,
    body: CandidateShortlistIn,
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    repo.upsert_candidate_shortlist(
        user.id,
        ticker,
        body.universe_group,
        body.status,
        memo=body.memo,
    )
    return {"ok": True, "ticker": ticker, "status": body.status}


@router.post("/{ticker}/add-watchlist", response_model=dict)
@router.post("/{ticker}/watchlist", response_model=dict)
def add_to_watchlist(
    ticker: str,
    background_tasks: BackgroundTasks,
    universe_group: str = "us",
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    row = _candidate_row(ticker, universe_group)
    if not row:
        raise HTTPException(status_code=404, detail="후보 종목을 찾을 수 없습니다.")
    raw = decode_raw_json(row.get("raw_json"))
    universe = raw.get("source_universe") or universe_group
    watchlist_id = repo.ensure_default_watchlist(user.id)
    repo.upsert_watchlist_item(
        user.id,
        watchlist_id,
        ticker,
        universe,
        name=row.get("name"),
    )
    repo.upsert_candidate_shortlist(user.id, ticker, universe_group, "added")
    background_tasks.add_task(_prefetch_choicestock_public_summary, ticker)
    return {
        "ok": True,
        "ticker": ticker,
        "watchlist_id": watchlist_id,
        "universe": universe,
    }


def _candidate_row(ticker: str, universe_group: str) -> dict | None:
    rows = repo.get_latest_candidate_scores(universe_group=universe_group)
    for row in rows:
        if row["ticker"] == ticker:
            return row
    return None


def _enrich(row: dict, shortlist: dict, watchlist_tickers: set[str]) -> dict:
    raw = decode_raw_json(row.get("raw_json"))
    key = (row["ticker"], row["universe_group"])
    state = shortlist.get(key)
    in_watchlist = row["ticker"] in watchlist_tickers
    status = "added" if in_watchlist else state.get("status") if state else "new"
    return {
        **row,
        "status": status,
        "status_memo": state.get("memo") if state else None,
        "in_watchlist": in_watchlist,
        "source_universe": raw.get("source_universe"),
        "source_universes": raw.get("source_universes") or [],
        "is_tech": bool(raw.get("is_tech")),
        "raw_forward_pe": raw.get("raw_fwd_pe"),
        "raw_peg": raw.get("raw_peg"),
        "raw_roe": raw.get("raw_roe"),
        "raw_rsi": raw.get("raw_rsi"),
        "raw_market_cap": raw.get("raw_market_cap_usd_m") or raw.get("raw_market_cap_krw"),
        "raw_fwd_eps_growth": raw.get("raw_fwd_eps_growth"),
        "raw_fwd_rev_growth": raw.get("raw_fwd_rev_growth"),
        "above_ma200": raw.get("above_ma200"),
    }


def _matches_sector(row: dict, sector: str) -> bool:
    if sector == "all":
        return True
    if row["region"] == "KR":
        return True
    return bool(row.get("is_tech"))


def _matches_source(row: dict, source: str) -> bool:
    if source == "all":
        return True
    sources = set(row.get("source_universes") or [])
    return source in sources or source == row.get("source_universe")


def _matches_status(row: dict, status: str) -> bool:
    if status == "all":
        return True
    if status == "new":
        return row.get("status") == "new" and not row.get("in_watchlist")
    return row.get("status") == status


def _limit_by_region(rows: list[dict], region: str, source: str, limit: int) -> list[dict]:
    limit = max(1, min(limit, 200))
    if source != "all" or region == "US":
        return rows[:limit]
    if region == "KR":
        return rows[:limit]
    selected = _pick_source_buckets(rows, [
        ("russell1000", 10),
        ("nasdaq100", 10),
        ("sp500", 10),
        ("kospi200", 10),
        ("kosdaq150", 10),
    ])
    return sorted(selected, key=lambda row: row.get("candidate_score") or -1, reverse=True)[:limit]


def _pick_source_buckets(rows: list[dict], buckets: list[tuple[str, int]]) -> list[dict]:
    selected = []
    seen: set[str] = set()
    for source, bucket_limit in buckets:
        bucket = [
            row for row in rows
            if row["ticker"] not in seen
            and _matches_source(row, source)
        ][:bucket_limit]
        selected.extend(bucket)
        seen.update(row["ticker"] for row in bucket)
    return selected


def _matches_numeric_filters(
    row: dict,
    *,
    min_growth_score: float | None,
    min_quality_score: float | None,
    min_valuation_score: float | None,
    min_momentum_score: float | None,
    min_timing_score: float | None,
    min_liquidity_score: float | None,
    min_market_cap: float | None,
    max_forward_pe: float | None,
    max_peg: float | None,
    min_roe: float | None,
    max_rsi: float | None,
    require_above_ma200: bool,
    positive_eps_growth: bool,
    positive_revenue_growth: bool,
) -> bool:
    checks = (
        ("growth_score", min_growth_score, "min"),
        ("quality_score", min_quality_score, "min"),
        ("valuation_score", min_valuation_score, "min"),
        ("momentum_score", min_momentum_score, "min"),
        ("timing_score", min_timing_score, "min"),
        ("liquidity_score", min_liquidity_score, "min"),
        ("raw_market_cap", min_market_cap, "min"),
        ("raw_forward_pe", max_forward_pe, "max"),
        ("raw_peg", max_peg, "max"),
        ("raw_roe", min_roe, "min"),
        ("raw_rsi", max_rsi, "max"),
    )
    for key, threshold, mode in checks:
        if threshold is None:
            continue
        value = row.get(key)
        if value is None:
            return False
        numeric = float(value)
        if mode == "min" and numeric < threshold:
            return False
        if mode == "max" and numeric > threshold:
            return False
    if require_above_ma200 and row.get("above_ma200") is not True:
        return False
    if positive_eps_growth and not _positive(row.get("raw_fwd_eps_growth")):
        return False
    if positive_revenue_growth and not _positive(row.get("raw_fwd_rev_growth")):
        return False
    return True


def _positive(value) -> bool:
    if value is None:
        return False
    return float(value) > 0


def _rerank_with_weights(rows: list[dict], weights: dict[str, float]) -> list[dict]:
    active_weights = {
        key: max(0.0, float(value or 0))
        for key, value in weights.items()
    }
    if sum(active_weights.values()) <= 0:
        active_weights = {
            "growth_score": 25,
            "quality_score": 20,
            "valuation_score": 15,
            "momentum_score": 20,
            "timing_score": 15,
            "liquidity_score": 5,
        }
    scored = []
    for row in rows:
        total = 0.0
        weight_sum = 0.0
        for key, weight in active_weights.items():
            value = row.get(key)
            if value is None or weight <= 0:
                continue
            total += float(value) * weight
            weight_sum += weight
        candidate_score = round(total / weight_sum, 1) if weight_sum else None
        scored.append({**row, "candidate_score": candidate_score})
    scored.sort(
        key=lambda row: (row["candidate_score"] is not None, row["candidate_score"] or -1),
        reverse=True,
    )
    for idx, row in enumerate(scored, start=1):
        row["rank"] = idx
    return scored


def _watchlist_tickers(user_id: int) -> set[str]:
    watchlist_id = repo.ensure_default_watchlist(user_id)
    return {item["ticker"] for item in repo.list_watchlist_items(user_id, watchlist_id)}


def _prefetch_choicestock_public_summary(ticker: str) -> None:
    if os.getenv("CHOICESTOCK_PREFETCH_DISABLED", "").lower() in ("1", "true", "yes"):
        return
    try:
        get_public_summary(ticker)
    except Exception as exc:
        log.warning("ChoiceStock 선수집 실패 (%s): %s", ticker, exc)
