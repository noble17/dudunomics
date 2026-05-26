from datetime import datetime
from fastapi import APIRouter, Depends
from api.auth import require_auth
from api.models import PortfolioRow, PortfolioSnapshot, SnapshotHistory, EventIn, EventOut
import core.repository as repo
from core.fx import get_fx_provider
from core.prices.kis import KISPriceProvider

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(require_auth)])

_price_provider = KISPriceProvider()
_fx_provider = get_fx_provider()


@router.get("/current", response_model=PortfolioSnapshot)
def get_current():
    holdings = repo.get_holdings()
    if not holdings:
        return PortfolioSnapshot(
            rows=[], total_equity_krw=0, total_with_cash_krw=0,
            total_equity_usd=0, total_with_cash_usd=0,
            cash_krw=0, cash_usd=0, usdkrw=1350.0, updated_at=datetime.now()
        )

    tickers = [h["ticker"] for h in holdings]
    markets = {h["ticker"]: h.get("market") for h in holdings}
    prices = _price_provider.get_current_prices(tickers, markets=markets)
    usdkrw = _get_usdkrw()

    cash_krw = float(repo.get_meta("cash_krw") or 0)
    cash_usd = float(repo.get_meta("cash_usd") or 0)
    cash_total_krw = cash_krw + cash_usd * usdkrw
    cash_total_usd = cash_krw / usdkrw + cash_usd

    rows: list[PortfolioRow] = []
    total_equity_krw = 0.0
    total_equity_usd = 0.0

    for h in holdings:
        ticker = h["ticker"]
        if ticker not in prices:
            continue
        p = prices[ticker]
        mv = p.current * h["quantity"]
        mv_krw = mv if p.currency == "KRW" else mv * usdkrw
        mv_usd = mv / usdkrw if p.currency == "KRW" else mv
        total_equity_krw += mv_krw
        total_equity_usd += mv_usd
        ret_pct = (p.current - h["avg_price"]) / h["avg_price"] * 100 if h["avg_price"] else 0
        rows.append(PortfolioRow(
            ticker=ticker, name=h["name"], quantity=h["quantity"],
            avg_price=h["avg_price"], current_price=p.current,
            currency=p.currency, market_value_krw=mv_krw,
            return_pct=round(ret_pct, 2), weight_pct=0,
            sector=h.get("sector"),
        ))

    denom = total_equity_krw or 1
    for r in rows:
        r.weight_pct = round(r.market_value_krw / denom * 100, 2)

    return PortfolioSnapshot(
        rows=rows,
        total_equity_krw=total_equity_krw,
        total_with_cash_krw=total_equity_krw + cash_total_krw,
        total_equity_usd=total_equity_usd,
        total_with_cash_usd=total_equity_usd + cash_total_usd,
        cash_krw=cash_total_krw,
        cash_usd=cash_total_usd,
        usdkrw=usdkrw,
        updated_at=datetime.now(),
    )


@router.get("/history", response_model=list[SnapshotHistory])
def get_history(limit: int = 400):
    rows = repo.get_snapshots(limit=limit)
    return [
        SnapshotHistory(
            ts=r["ts"],
            total_equity_krw=r["total_equity_krw"],
            total_with_cash_krw=r["total_with_cash_krw"],
            total_equity_usd=r["total_equity_usd"],
            total_with_cash_usd=r["total_with_cash_usd"],
        )
        for r in rows
    ]


@router.get("/events", response_model=list[EventOut])
def get_events():
    return repo.get_events()


@router.post("/events", response_model=EventOut)
def add_event(body: EventIn):
    event_id = repo.insert_event(
        ts=body.ts, label=body.label, amount=body.amount, type_=body.type
    )
    return EventOut(id=event_id, ts=body.ts, label=body.label, amount=body.amount, type=body.type)


@router.delete("/events/{event_id}")
def delete_event(event_id: int):
    repo.delete_event(event_id)
    return {"ok": True}


def _get_usdkrw() -> float:
    cached = repo.get_latest_fx_rate("USDKRW")
    if cached:
        return cached
    try:
        return _fx_provider.get_rate("USDKRW")
    except Exception:
        return 1350.0
