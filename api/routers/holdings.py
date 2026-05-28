import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from api.models import CashUpdate, HoldingIn, HoldingOut, TickerLookupOut, TickerSearchHit
from core.prices.kis import KISPriceProvider
import core.repository as repo

_price_provider = KISPriceProvider()

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("/lookup/{ticker}", response_model=TickerLookupOut)
def lookup_ticker(ticker: str, market: str | None = Query(default=None),
                  user: CurrentUser = Depends(current_user)):
    result = _price_provider.lookup(ticker, market=market)
    if result is None:
        raise HTTPException(status_code=422, detail={"need_market": True})
    return result


@router.get("/search", response_model=list[TickerSearchHit])
def search_tickers(q: str = Query(..., min_length=1),
                   user: CurrentUser = Depends(current_user)):
    return _price_provider.search(q)


@router.get("", response_model=list[HoldingOut])
def list_holdings(user: CurrentUser = Depends(current_user)):
    return repo.get_holdings(user.id)


@router.get("/cash")
def get_cash(user: CurrentUser = Depends(current_user)):
    return {
        "cash_krw": float(repo.get_meta(user.id, "cash_krw") or 0),
        "cash_usd": float(repo.get_meta(user.id, "cash_usd") or 0),
    }


@router.put("/cash")
def update_cash(body: CashUpdate, user: CurrentUser = Depends(current_user)):
    repo.set_meta(user.id, "cash_krw", str(body.cash_krw))
    repo.set_meta(user.id, "cash_usd", str(body.cash_usd))
    return {"ok": True}


@router.put("/{ticker}", response_model=HoldingOut)
def upsert_holding(ticker: str, body: HoldingIn,
                   user: CurrentUser = Depends(current_user)):
    repo.upsert_holding(
        user_id=user.id,
        ticker=ticker,
        name=body.name,
        currency=body.currency,
        quantity=body.quantity,
        avg_price=body.avg_price,
        sector=body.sector,
        market=body.market,
    )
    rows = repo.get_holdings(user.id)
    row = next((r for r in rows if r["ticker"] == ticker), None)
    if not row:
        raise HTTPException(status_code=404)
    return row


@router.delete("/{ticker}")
def delete_holding(ticker: str, user: CurrentUser = Depends(current_user)):
    repo.delete_holding(user.id, ticker)
    _backup_json(user.id)
    return {"ok": True}


def _backup_json(user_id: int):
    root = Path(__file__).parent.parent.parent
    path = root / "data" / "holdings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    holdings = repo.get_holdings(user_id)
    payload = {
        "holdings": [{"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
                      "quantity": r["quantity"], "avg_price": r["avg_price"]} for r in holdings],
        "cash_krw": float(repo.get_meta(user_id, "cash_krw") or 0),
        "cash_usd": float(repo.get_meta(user_id, "cash_usd") or 0),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
