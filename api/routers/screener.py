"""api/routers/screener.py — 퀀트 스크리너 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from api.auth import require_auth
from api.models import QuantScoreOut, TickerNoteIn, TickerNoteOut
import core.repository as repo

router = APIRouter(
    prefix="/api/screener",
    tags=["screener"],
    dependencies=[Depends(require_auth)],
)


@router.get("/scores", response_model=list[QuantScoreOut])
def get_scores(universe: str = "sp500"):
    """유니버스 전체 최신 퀀트 스코어 반환. 프론트엔드 최초 로드 시 1회 호출."""
    rows = repo.get_latest_quant_scores(universe)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"유니버스 '{universe}' 데이터 없음. /api/screener/refresh 먼저 실행 필요."
        )
    return rows


@router.get("/ticker/{ticker}", response_model=QuantScoreOut)
def get_ticker(ticker: str, universe: str = "sp500"):
    """단일 종목 상세 퀀트 스코어 반환."""
    row = repo.get_quant_ticker(ticker.upper(), universe)
    if not row:
        raise HTTPException(status_code=404, detail=f"{ticker} 데이터 없음")
    return row


@router.post("/refresh")
def refresh(universe: str = "sp500", background_tasks: BackgroundTasks = None):
    """배치 스코어링 트리거. 백그라운드로 실행."""
    from core.scoring.universe_scorer import run_batch

    def _run():
        try:
            run_batch(universe)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("배치 실패: %s", e)

    if background_tasks:
        background_tasks.add_task(_run)
        return {"status": "started", "universe": universe}
    else:
        result = run_batch(universe)
        return result


@router.get("/notes/{ticker}", response_model=TickerNoteOut | None)
def get_note(ticker: str):
    return repo.get_ticker_note(ticker.upper())


@router.put("/notes/{ticker}", response_model=TickerNoteOut)
def upsert_note(ticker: str, body: TickerNoteIn):
    t = ticker.upper()
    repo.upsert_ticker_note(
        ticker=t,
        opinion=body.opinion,
        target_price=body.target_price,
        memo=body.memo,
        tags=body.tags,
    )
    row = repo.get_ticker_note(t)
    return row
