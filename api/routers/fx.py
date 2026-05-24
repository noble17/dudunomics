from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.models import FxRateOut
import core.repository as repo
from core.fx import get_fx_provider

router = APIRouter(prefix="/api/fx", tags=["fx"], dependencies=[Depends(require_auth)])
_fx_provider = get_fx_provider()

@router.get("/{pair}", response_model=FxRateOut)
def get_fx_rate(pair: str):
    pair = pair.upper()
    cached = repo.get_latest_fx_rate(pair)
    if cached:
        return FxRateOut(pair=pair, rate=cached)
    try:
        rate = _fx_provider.get_rate(pair)
        return FxRateOut(pair=pair, rate=rate)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"환율 조회 실패: {e}")
