"""api/routers/screener.py — 퀀트 스크리너 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from core.auth.deps import current_user, CurrentUser
from api.models import QuantScoreOut, TickerNoteIn, TickerNoteOut
import core.repository as repo

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/scores", response_model=list[QuantScoreOut])
def get_scores(universe: str = "sp500", user: CurrentUser = Depends(current_user)):
    rows = repo.get_latest_quant_scores(universe)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"유니버스 '{universe}' 데이터 없음. /api/screener/refresh 먼저 실행 필요."
        )
    return rows


@router.get("/ticker/{ticker}", response_model=QuantScoreOut)
def get_ticker(ticker: str, universe: str = "sp500",
               user: CurrentUser = Depends(current_user)):
    row = repo.get_quant_ticker(ticker.upper(), universe)
    if not row:
        raise HTTPException(status_code=404, detail=f"{ticker} 데이터 없음")
    return row


@router.get("/status")
def batch_status(universe: str = "sp500", user: CurrentUser = Depends(current_user)):
    from core.batch_refresh import get_status
    return get_status(universe)


@router.post("/refresh")
def refresh(universe: str = "sp500", force: bool = False, background_tasks: BackgroundTasks = None,
            user: CurrentUser = Depends(current_user)):
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


@router.post("/ticker/{ticker}/refresh-fields")
def refresh_ticker_fields(ticker: str, universe: str = "sp500",
                          user: CurrentUser = Depends(current_user)):
    """단일 종목의 펀더멘탈 필드만 즉시 재페치하여 DB 갱신 (캐시 무효화 후)."""
    from core.data.fundamentals_extended import _fetch_one
    from datetime import date

    t = ticker.upper()
    current = repo.get_quant_ticker(t, universe)
    if not current:
        raise HTTPException(status_code=404, detail=f"{t} 데이터 없음")

    snap = _fetch_one(t, date.today())
    row = dict(current)
    row["raw_eps_ttm"] = snap.eps_ttm
    row["raw_roe"] = snap.roe if snap.roe is not None else row.get("raw_roe")
    row["raw_fwd_eps"] = snap.forward_eps if snap.forward_eps is not None else row.get("raw_fwd_eps")
    row["raw_fwd_pe"] = snap.forward_pe if snap.forward_pe is not None else row.get("raw_fwd_pe")
    row["raw_trailing_pe"] = snap.trailing_pe if snap.trailing_pe is not None else row.get("raw_trailing_pe")
    repo.upsert_quant_scores([row])
    return {"ticker": t, "raw_eps_ttm": snap.eps_ttm, "raw_roe": row["raw_roe"],
            "raw_fwd_eps": row["raw_fwd_eps"]}


@router.get("/notes/{ticker}", response_model=TickerNoteOut | None)
def get_note(ticker: str, user: CurrentUser = Depends(current_user)):
    return repo.get_ticker_note(user.id, ticker.upper())


@router.put("/notes/{ticker}", response_model=TickerNoteOut)
def upsert_note(ticker: str, body: TickerNoteIn,
                user: CurrentUser = Depends(current_user)):
    t = ticker.upper()
    repo.upsert_ticker_note(
        user_id=user.id,
        ticker=t,
        opinion=body.opinion,
        target_price=body.target_price,
        memo=body.memo,
        tags=body.tags,
    )
    return repo.get_ticker_note(user.id, t)
