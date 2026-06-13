# api/routers/trades.py
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from core.auth.deps import current_user, CurrentUser
from api.models import SyncResult, TradeImportPreview, TradeImportRow, TradeIn, TradeOut
from core.data.isin_resolver import resolve_isin
from core.data.toss_statement_import import parse_toss_statement_pdf
from core.prices.toss import fetch_orders as fetch_toss_orders
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


@router.post("/import-toss-pdf/preview", response_model=TradeImportPreview)
async def preview_toss_pdf(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="PDF 파일만 업로드할 수 있습니다.")
    try:
        parsed, errors = parse_toss_statement_pdf(await file.read())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Toss PDF 파싱 실패: {e}") from e

    resolved: dict[str, dict | None] = {}
    for item in parsed:
        if item.needs_mapping and item.raw_symbol:
            resolved.setdefault(item.raw_symbol, resolve_isin(item.raw_symbol))

    rows = [
        TradeImportRow(
            row_id=item.row_id,
            ticker=(resolved.get(item.raw_symbol) or {}).get("ticker") or item.ticker,
            market=(resolved.get(item.raw_symbol) or {}).get("market") or item.market,
            trade_type=item.trade_type,
            quantity=item.quantity,
            price=item.price,
            currency=item.currency,
            traded_at=item.traded_at,
            fee=item.fee,
            note=item.note,
            name=(resolved.get(item.raw_symbol) or {}).get("name") or item.name,
            raw_symbol=item.raw_symbol,
            needs_mapping=item.needs_mapping and not bool(resolved.get(item.raw_symbol)),
        )
        for item in parsed
    ]
    return TradeImportPreview(rows=rows, errors=errors)


@router.post("/import-toss-pdf/commit", response_model=SyncResult)
def commit_toss_pdf_import(
    body: TradeImportPreview,
    user: CurrentUser = Depends(current_user),
):
    errors: list[str] = []
    before = len(repo.get_trades(user.id))
    for row in body.rows:
        ticker = row.ticker.strip().upper()
        if not ticker:
            errors.append(f"{row.traded_at} {row.name or row.raw_symbol}: 티커가 필요합니다.")
            continue
        repo.create_trade(
            user_id=user.id,
            ticker=ticker,
            market=row.market,
            trade_type=row.trade_type,
            quantity=row.quantity,
            price=row.price,
            currency=row.currency,
            traded_at=row.traded_at,
            fee=row.fee,
            note=row.note,
            source="toss_import",
            external_id=row.row_id,
            sync_holdings=False,
        )
    after = len(repo.get_trades(user.id))
    return SyncResult(added=max(after - before, 0), updated=0, errors=errors)


@router.post("/sync-from-toss", response_model=SyncResult)
def sync_from_toss(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    status: str = Query(default="OPEN"),
    user: CurrentUser = Depends(current_user),
):
    try:
        items = fetch_toss_orders(start_date=start_date, end_date=end_date, status=status)
    except Exception as e:
        return SyncResult(added=0, updated=0, errors=[f"Toss 거래내역 동기화 실패: {e}"])

    before = len(repo.get_trades(user.id))
    for item in items:
        repo.create_trade(
            user_id=user.id,
            ticker=item["ticker"],
            market=item.get("market"),
            trade_type=item["trade_type"],
            quantity=item["quantity"],
            price=item["price"],
            currency=item["currency"],
            traded_at=item["traded_at"],
            fee=item.get("fee", 0),
            note=item.get("note"),
            source="toss",
            external_id=item["external_id"],
            sync_holdings=False,
        )
    after = len(repo.get_trades(user.id))
    return SyncResult(added=max(after - before, 0), updated=0, errors=[])


@router.delete("/{trade_id}", status_code=200)
def delete_trade(trade_id: int, user: CurrentUser = Depends(current_user)):
    try:
        ok = repo.delete_trade(user.id, trade_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    return {"ok": True}
