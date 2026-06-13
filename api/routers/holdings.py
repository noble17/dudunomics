import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from api.models import CashUpdate, HoldingIn, HoldingOut, HoldingSourceMetaUpdate, TickerLookupOut, TickerSearchHit, TargetWeightUpdate, SyncResult
from core.prices.toss import fetch_buying_power as fetch_toss_buying_power
from core.prices.toss import fetch_holdings as fetch_toss_holdings
from core.prices.toss import TossPriceProvider
import core.repository as repo

_price_provider = TossPriceProvider()

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
    return _search_tickers(q)


@router.get("", response_model=list[HoldingOut])
def list_holdings(user: CurrentUser = Depends(current_user)):
    return repo.get_holdings(user.id, include_excluded=True)


@router.get("/cash")
def get_cash(user: CurrentUser = Depends(current_user)):
    manual = repo.get_cash_source(user.id, "manual")
    total = repo.get_cash_total(user.id)
    return {
        "cash_krw": manual["cash_krw"],
        "cash_usd": manual["cash_usd"],
        "total_cash_krw": total["cash_krw"],
        "total_cash_usd": total["cash_usd"],
        "sources": repo.get_cash_sources(user.id),
    }


@router.put("/cash")
def update_cash(body: CashUpdate, user: CurrentUser = Depends(current_user)):
    repo.set_cash_source(user.id, "manual", body.cash_krw, body.cash_usd)
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


@router.patch("/{ticker}")
def patch_holding(ticker: str, body: TargetWeightUpdate,
                  user: CurrentUser = Depends(current_user)):
    holdings = repo.get_holdings(user.id)
    if not any(h["ticker"] == ticker for h in holdings):
        raise HTTPException(status_code=404, detail="보유 종목을 찾을 수 없습니다.")
    repo.set_holding_target_weight(user.id, ticker, body.target_weight)

    updated = repo.get_holdings(user.id)
    total_target = sum(
        h.get("target_weight") or 0 for h in updated if h.get("target_weight") is not None
    )
    warning = total_target > 100
    return {"ok": True, "total_target_weight": round(total_target, 2), "over_100": warning}


@router.patch("/{ticker}/source-meta", response_model=HoldingOut)
def patch_holding_source_meta(ticker: str, body: HoldingSourceMetaUpdate,
                              user: CurrentUser = Depends(current_user)):
    ok = repo.update_holding_source_meta(
        user_id=user.id,
        ticker=ticker,
        source=body.source,
        account_id=body.account_id,
        name=body.name,
        sector=body.sector,
        excluded_from_portfolio=body.excluded_from_portfolio,
    )
    if not ok:
        raise HTTPException(status_code=404)
    rows = repo.get_holdings(user.id, include_excluded=True)
    row = next((r for r in rows if r["ticker"] == ticker), None)
    if not row:
        raise HTTPException(status_code=404)
    return row


@router.post("/sync-from-kis", response_model=SyncResult)
def sync_from_kis(user: CurrentUser = Depends(current_user)):
    return SyncResult(added=0, updated=0, errors=["KIS 동기화는 Toss 동기화로 대체되었습니다."])


@router.post("/sync-from-toss", response_model=SyncResult)
def sync_from_toss(user: CurrentUser = Depends(current_user)):
    try:
        items = fetch_toss_holdings()
    except Exception as e:
        return SyncResult(added=0, updated=0, errors=[f"Toss 동기화 실패: {e}"])
    cash_errors = _sync_toss_cash(user.id)
    if not items:
        return SyncResult(added=0, updated=0, errors=cash_errors)
    result = _sync_holdings(user.id, items, source="toss")
    result.errors.extend(cash_errors)
    return result


def _sync_toss_cash(user_id: int) -> list[str]:
    try:
        repo.set_cash_source(
            user_id,
            "toss",
            fetch_toss_buying_power("KRW"),
            fetch_toss_buying_power("USD"),
        )
    except Exception as e:
        return [f"Toss 현금 동기화 실패: {e}"]
    return []


def _sync_holdings(user_id: int, items: list[dict], source: str) -> SyncResult:
    existing = {h["ticker"] for h in repo.get_holdings(user_id)}
    added, updated, errors = 0, 0, []

    for item in items:
        try:
            repo.upsert_holding(
                user_id=user_id,
                source=source,
                preserve_display_fields=(source == "toss"),
                **item,
            )
            if item["ticker"] in existing:
                updated += 1
            else:
                added += 1
        except Exception as e:
            errors.append(f"{item['ticker']}: {e}")

    return SyncResult(added=added, updated=updated, errors=errors)


def _search_tickers(query: str, max_results: int = 8) -> list[dict]:
    try:
        from core.data.search_provider import search as search_provider
        results = search_provider(query, max_results=max_results)
    except Exception:
        results = []

    hits: list[dict] = []
    for row in results:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        lookup = _price_provider.lookup(ticker)
        if not lookup:
            lookup = {
                "ticker": ticker,
                "name": row.get("name") or ticker,
                "market": _market_from_exchange(str(row.get("exchange") or "")),
                "currency": "KRW" if ticker.endswith((".KS", ".KQ")) or ticker.isdigit() else "USD",
            }
        hits.append({
            "ticker": lookup["ticker"],
            "name": lookup["name"],
            "exchange": row.get("exchange") or lookup.get("market") or "",
            "market": lookup.get("market") or "",
            "type": row.get("type") or "",
        })
        if len(hits) >= max_results:
            break
    return hits


def _market_from_exchange(exchange: str) -> str:
    upper = exchange.upper()
    if "NASDAQ" in upper or upper in ("NMS", "NGM", "NCM"):
        return "NASDAQ"
    if "NYSE" in upper or upper == "NYQ":
        return "NYSE"
    if "AMEX" in upper or "ARCA" in upper or upper in ("ASE", "PCX"):
        return "AMEX"
    if "KRX" in upper or "KOSPI" in upper or "KOSDAQ" in upper or upper in ("KSC", "KOE"):
        return "KRX"
    return ""


def _backup_json(user_id: int):
    root = Path(__file__).parent.parent.parent
    path = root / "data" / "holdings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    holdings = repo.get_holdings(user_id)
    payload = {
        "holdings": [{"ticker": r["ticker"], "name": r["name"], "currency": r["currency"],
                      "quantity": r["quantity"], "avg_price": r["avg_price"]} for r in holdings],
        "cash_krw": repo.get_cash_total(user_id)["cash_krw"],
        "cash_usd": repo.get_cash_total(user_id)["cash_usd"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
