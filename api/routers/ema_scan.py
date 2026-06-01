from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from core.ema_scan import run_ema_scan

router = APIRouter(prefix="/api/ema-scan", tags=["ema-scan"])


@router.post("/run")
async def trigger_ema_scan(
    background_tasks: BackgroundTasks,
    market: str = Query(..., description="KR 또는 US"),
    user: CurrentUser = Depends(current_user),
):
    """EMA 골든크로스 스캔 즉시 실행 (백그라운드). Telegram 발송 포함."""
    if market not in ("KR", "US"):
        raise HTTPException(status_code=400, detail="market은 KR 또는 US")
    background_tasks.add_task(run_ema_scan, market)
    return {"status": "started", "market": market}
