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
    limit: int = 50,
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
        if _matches_sector(row, sector) and _matches_status(row, status)
    ]
    return filtered[: max(1, min(limit, 200))]


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
    }


def _matches_sector(row: dict, sector: str) -> bool:
    if sector == "all":
        return True
    if row["region"] == "KR":
        return True
    return bool(row.get("is_tech"))


def _matches_status(row: dict, status: str) -> bool:
    if status == "all":
        return True
    if status == "new":
        return row.get("status") == "new" and not row.get("in_watchlist")
    return row.get("status") == status


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
