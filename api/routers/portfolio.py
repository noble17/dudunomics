from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from core.auth.deps import current_user, CurrentUser
from api.models import PortfolioRow, PortfolioSnapshot, SnapshotHistory, EventIn, EventOut, PerformanceOut, BenchmarkStats, PerformanceChartPoint, RebalancingRow
import core.repository as repo
from core.fx import get_fx_provider
from core.prices.kis import KISPriceProvider
from core.data.ohlcv_cache import fetch_index

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_price_provider = KISPriceProvider()
_fx_provider = get_fx_provider()


@router.get("/current", response_model=PortfolioSnapshot)
def get_current(user: CurrentUser = Depends(current_user)):
    holdings = repo.get_holdings(user.id)
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

    cash_krw = float(repo.get_meta(user.id, "cash_krw") or 0)
    cash_usd = float(repo.get_meta(user.id, "cash_usd") or 0)
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
def get_history(limit: int = 400, user: CurrentUser = Depends(current_user)):
    rows = repo.get_snapshots(user.id, limit=limit)
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
def get_events(user: CurrentUser = Depends(current_user)):
    return repo.get_events(user.id)


@router.post("/events", response_model=EventOut)
def add_event(body: EventIn, user: CurrentUser = Depends(current_user)):
    event_id = repo.insert_event(
        user_id=user.id,
        ts=body.ts, label=body.label, amount=body.amount, type_=body.type
    )
    return EventOut(id=event_id, ts=body.ts, label=body.label, amount=body.amount, type=body.type)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, user: CurrentUser = Depends(current_user)):
    repo.delete_event(user.id, event_id)
    return {"ok": True}


@router.get("/performance", response_model=PerformanceOut)
def get_performance(
    period: str = "6m",
    user: CurrentUser = Depends(current_user),
):
    if period not in ("1m", "3m", "6m", "1y", "all"):
        period = "6m"

    equity_series = repo.get_portfolio_returns(user.id, period)
    metrics = repo.calc_performance(equity_series)

    benchmark: dict[str, BenchmarkStats] = {}
    chart: list[PerformanceChartPoint] = []

    try:
        days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "all": 1825}[period]
        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        kospi_series = fetch_index("^KS11", start=start_date, end=end_date)
        sp500_series = fetch_index("^GSPC", start=start_date, end=end_date)

        def to_cum_return(series) -> dict[str, float]:
            if series.empty:
                return {}
            base = float(series.iloc[0])
            return {str(d.date() if hasattr(d, "date") else d): round((float(v) - base) / base * 100, 2)
                    for d, v in series.items() if base > 0}

        kospi_map = to_cum_return(kospi_series)
        sp500_map = to_cum_return(sp500_series)

        port_map: dict[str, float] = {}
        if equity_series:
            base = equity_series[0]["equity"]
            for e in equity_series:
                if base > 0:
                    port_map[e["date"]] = round((e["equity"] - base) / base * 100, 2)

        all_dates = sorted(set(port_map) | set(kospi_map) | set(sp500_map))
        chart = [
            PerformanceChartPoint(
                date=d,
                portfolio=port_map.get(d, 0.0),
                kospi=kospi_map.get(d, 0.0),
                sp500=sp500_map.get(d, 0.0),
            )
            for d in all_dates
        ]

        def bench_total(m: dict) -> float:
            vals = list(m.values())
            return vals[-1] if vals else 0.0

        benchmark = {
            "kospi": BenchmarkStats(return_pct=bench_total(kospi_map), correlation=0.0),
            "sp500": BenchmarkStats(return_pct=bench_total(sp500_map), correlation=0.0),
        }
    except Exception:
        pass

    return PerformanceOut(
        sharpe=metrics["sharpe"],
        mdd=metrics["mdd"],
        total_return=metrics["total_return"],
        annualized_return=metrics["annualized_return"],
        benchmark=benchmark,
        chart=chart,
    )


@router.get("/rebalancing", response_model=list[RebalancingRow])
def get_rebalancing(user: CurrentUser = Depends(current_user)):
    holdings = repo.get_holdings(user.id)
    if not holdings:
        return []

    tickers = [h["ticker"] for h in holdings]
    markets = {h["ticker"]: h.get("market") for h in holdings}
    prices = _price_provider.get_current_prices(tickers, markets=markets)
    usdkrw = _get_usdkrw()

    total_krw = 0.0
    mv_map: dict[str, float] = {}
    for h in holdings:
        ticker = h["ticker"]
        if ticker not in prices:
            continue
        p = prices[ticker]
        mv = p.current * h["quantity"]
        mv_krw = mv if p.currency == "KRW" else mv * usdkrw
        mv_map[ticker] = mv_krw
        total_krw += mv_krw

    rows: list[RebalancingRow] = []
    for h in holdings:
        ticker = h["ticker"]
        mv_krw = mv_map.get(ticker, 0.0)
        current_w = round(mv_krw / total_krw * 100, 2) if total_krw > 0 else 0.0
        target_w = h.get("target_weight")

        if target_w is None:
            action = "NO_TARGET"
            diff = None
            amount = 0.0
        else:
            diff = round(target_w - current_w, 2)
            amount = abs(diff / 100 * total_krw)
            if abs(diff) < 0.5:
                action = "HOLD"
            elif diff > 0:
                action = "BUY"
            else:
                action = "SELL"

        rows.append(RebalancingRow(
            ticker=ticker,
            name=h["name"],
            current_weight=current_w,
            target_weight=target_w,
            diff_weight=diff,
            action=action,
            amount_krw=round(amount),
        ))

    return sorted(rows, key=lambda r: abs(r.diff_weight or 0), reverse=True)


def _get_usdkrw() -> float:
    cached = repo.get_latest_fx_rate("USDKRW")
    if cached:
        return cached
    try:
        return _fx_provider.get_rate("USDKRW")
    except Exception:
        return 1350.0
