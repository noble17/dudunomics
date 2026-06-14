"""사용자 Watchlist 관리 엔드포인트."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.models import WatchlistIn, WatchlistItemIn, WatchlistItemOut, WatchlistMembershipOut, WatchlistOut
from core.analytics.ticker_performance import build_ticker_performance
from core.auth.deps import CurrentUser, current_user
from core.data.choicestock_public import get_public_summary
from core.scoring.technical_timing import analyze_timing
import core.repository as repo


router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])
log = logging.getLogger(__name__)


@router.get("", response_model=list[WatchlistOut])
def list_watchlists(user: CurrentUser = Depends(current_user)):
    return repo.list_watchlists(user.id)


@router.post("", response_model=WatchlistOut)
def create_watchlist(body: WatchlistIn, user: CurrentUser = Depends(current_user)):
    return repo.create_watchlist(user.id, body.name, body.description)


@router.patch("/{watchlist_id}", response_model=WatchlistOut)
def update_watchlist(watchlist_id: int, body: WatchlistIn, user: CurrentUser = Depends(current_user)):
    updated = repo.update_watchlist(user.id, watchlist_id, body.name, body.description)
    if not updated:
        raise HTTPException(status_code=404, detail="Watchlist를 찾을 수 없습니다.")
    return updated


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: int, user: CurrentUser = Depends(current_user)):
    repo.delete_watchlist(user.id, watchlist_id)
    return {"ok": True}


@router.get("/{watchlist_id}/items", response_model=list[WatchlistItemOut])
def list_items(watchlist_id: int, user: CurrentUser = Depends(current_user)):
    items = repo.list_watchlist_items(user.id, watchlist_id)
    if not repo.get_watchlist(user.id, watchlist_id):
        raise HTTPException(status_code=404, detail="Watchlist를 찾을 수 없습니다.")
    tickers = [item["ticker"] for item in items]
    names = {item["ticker"]: item.get("name") or item["ticker"] for item in items}
    performance = build_ticker_performance(tickers, names=names) if tickers else []
    item_by_key = {(item["ticker"], item["universe"]): item for item in items}
    item_by_ticker = {item["ticker"]: item for item in items}
    return [
        {
            **row,
            "watchlist_id": watchlist_id,
            **_watchlist_item_meta(row["ticker"], items, item_by_key),
            **_growth_meta(row["ticker"], item_by_ticker.get(row["ticker"], {}).get("universe", "sp500")),
            **_timing_meta(row["ticker"]),
        }
        for row in performance
    ]


@router.get("/memberships/{ticker}", response_model=list[WatchlistMembershipOut])
def list_memberships(ticker: str, user: CurrentUser = Depends(current_user)):
    return repo.list_watchlist_memberships(user.id, ticker.upper())


@router.put("/{watchlist_id}/items/{ticker}", response_model=dict)
def add_item(
    watchlist_id: int,
    ticker: str,
    body: WatchlistItemIn,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
):
    ticker = ticker.upper()
    try:
        repo.upsert_watchlist_item(
            user.id,
            watchlist_id,
            ticker,
            body.universe,
            name=body.name,
            memo=body.memo,
            timing_alert_enabled=body.timing_alert_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Watchlist를 찾을 수 없습니다.") from exc
    background_tasks.add_task(_prefetch_choicestock_public_summary, ticker)
    return {
        "ok": True,
        "watchlist_id": watchlist_id,
        "ticker": ticker,
        "universe": body.universe,
    }


def _prefetch_choicestock_public_summary(ticker: str) -> None:
    if os.getenv("CHOICESTOCK_PREFETCH_DISABLED", "").lower() in ("1", "true", "yes"):
        return
    try:
        get_public_summary(ticker)
    except Exception as exc:
        log.warning("ChoiceStock 선수집 실패 (%s): %s", ticker, exc)


@router.delete("/{watchlist_id}/items/{ticker}")
def remove_item(
    watchlist_id: int,
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    repo.remove_watchlist_item(user.id, watchlist_id, ticker.upper(), universe)
    return {"ok": True}


def _universe_for(ticker: str, items: list[dict]) -> str:
    for item in items:
        if item["ticker"] == ticker:
            return item["universe"]
    return "sp500"


def _watchlist_item_meta(ticker: str, items: list[dict], item_by_key: dict[tuple[str, str], dict]) -> dict:
    universe = _universe_for(ticker, items)
    item = item_by_key.get((ticker, universe), {})
    return {
        "universe": item.get("universe", universe),
        "memo": item.get("memo"),
        "timing_alert_enabled": bool(item.get("timing_alert_enabled")),
    }


def _growth_meta(ticker: str, universe: str) -> dict:
    row = repo.get_quant_ticker(ticker, universe)
    return {
        "growth_composite": row.get("growth_composite") if row else None,
    }


def _timing_meta(ticker: str) -> dict:
    try:
        timing = analyze_timing(ticker)
    except Exception:
        timing = {"status": "unknown"}
    return {
        "timing_status": timing.get("status"),
        "timing_aligned": timing.get("aligned"),
        "timing_pullback_stage": timing.get("pullback_stage"),
        "timing_volume_level": timing.get("volume_level"),
        "timing_volume_ratio": timing.get("volume_ratio"),
        "timing_rsi_level": timing.get("rsi_level"),
        "timing_rsi14": timing.get("rsi14"),
    }
