from fastapi import APIRouter, Depends, Query

import core.repository as repo
from api.models import GoldenCrossOut
from core.auth.deps import CurrentUser, current_user

router = APIRouter(prefix="/api/golden-cross", tags=["golden-cross"])


@router.get("", response_model=GoldenCrossOut)
def list_golden_crosses(
    market: str | None = Query(default=None, pattern="^(KR|US)$"),
    group_name: str | None = Query(default=None, pattern="^(KOSPI|KOSDAQ|US)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    _user: CurrentUser = Depends(current_user),
):
    active = []
    markets = [market] if market else ["KR", "US"]
    for item in markets:
        active.extend(repo.get_active_golden_crosses(item))
    if group_name:
        active = [row for row in active if row.get("group_name") == group_name]

    return {
        "active": active,
        "history": repo.list_golden_cross_history(market=market, group_name=group_name, limit=limit),
    }
