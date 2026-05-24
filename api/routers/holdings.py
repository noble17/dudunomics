import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.models import CashUpdate, HoldingIn, HoldingOut
import core.repository as repo

router = APIRouter(prefix="/api/holdings", tags=["holdings"], dependencies=[Depends(require_auth)])

@router.get("", response_model=list[HoldingOut])
def list_holdings():
    return repo.get_holdings()

@router.get("/cash")
def get_cash():
    return {
        "cash_krw": float(repo.get_meta("cash_krw") or 0),
        "cash_usd": float(repo.get_meta("cash_usd") or 0),
    }

@router.put("/cash")
def update_cash(body: CashUpdate):
    repo.set_meta("cash_krw", str(body.cash_krw))
    repo.set_meta("cash_usd", str(body.cash_usd))
    return {"ok": True}

@router.put("/{ticker}", response_model=HoldingOut)
def upsert_holding(ticker: str, body: HoldingIn):
    repo.upsert_holding(
        ticker=ticker,
        name=body.name,
        currency=body.currency,
        quantity=body.quantity,
        avg_price=body.avg_price,
    )
    rows = repo.get_holdings()
    row = next((r for r in rows if r["ticker"] == ticker), None)
    if not row:
        raise HTTPException(status_code=404)
    return row

@router.delete("/{ticker}")
def delete_holding(ticker: str):
    repo.delete_holding(ticker)
    _backup_json()
    return {"ok": True}

def _backup_json():
    root = Path(__file__).parent.parent.parent  # api/routers/holdings.py → project root
    path = root / "data" / "holdings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    holdings = repo.get_holdings()
    payload = {
        "holdings": [{"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
                      "quantity": r["quantity"], "avg_price": r["avg_price"]} for r in holdings],
        "cash_krw": float(repo.get_meta("cash_krw") or 0),
        "cash_usd": float(repo.get_meta("cash_usd") or 0),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
