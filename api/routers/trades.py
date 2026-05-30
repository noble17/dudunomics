# api/routers/trades.py
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from api.models import TradeIn, TradeOut
import core.repository as repo

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=list[TradeOut])
def list_trades(
    ticker: str | None = Query(default=None),
    user: CurrentUser = Depends(current_user),
):
    return repo.get_trades(user.id, ticker=ticker)


@router.post("", response_model=TradeOut, status_code=201)
def create_trade(body: TradeIn, user: CurrentUser = Depends(current_user)):
    if body.trade_type == "SELL":
        holdings = repo.get_holdings(user.id)
        holding = next((h for h in holdings if h["ticker"] == body.ticker), None)
        if not holding or holding["quantity"] < body.quantity:
            raise HTTPException(
                status_code=422,
                detail=f"{body.ticker} 보유 수량({holding['quantity'] if holding else 0})보다 매도 수량이 많습니다."
            )

    trade_id = repo.create_trade(
        user_id=user.id,
        ticker=body.ticker,
        market=body.market,
        trade_type=body.trade_type,
        quantity=body.quantity,
        price=body.price,
        currency=body.currency,
        traded_at=body.traded_at,
        fee=body.fee,
        note=body.note,
    )
    trades = repo.get_trades(user.id)
    trade = next(t for t in trades if t["id"] == trade_id)
    return trade


@router.delete("/{trade_id}", status_code=200)
def delete_trade(trade_id: int, user: CurrentUser = Depends(current_user)):
    ok = repo.delete_trade(user.id, trade_id)
    if not ok:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    return {"ok": True}
