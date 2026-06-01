"""api/routers/stock_detail.py — 종목 상세 재무/차트 엔드포인트."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from core.auth.deps import current_user, CurrentUser
from core.data.stockanalysis_financials import fetch_annual_financials
from core.data.fundamentals_scraper import fetch_fundamentals
from core.data.ohlcv_cache import fetch_ohlcv
import core.repository as repo

router = APIRouter(prefix="/api/screener/ticker", tags=["stock-detail"])


@router.get("/{ticker}/financials")
def get_financials(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    upper = ticker.upper()
    data = fetch_annual_financials(upper)
    if data is None:
        raise HTTPException(status_code=404, detail=f"{upper} 재무 데이터 없음 (국내 종목 미지원)")

    snap = fetch_fundamentals(upper)
    metrics: dict = {
        "market_cap_m": snap.market_cap_m if snap else None,
        "trailing_pe": snap.trailing_pe if snap else None,
        "forward_pe": snap.forward_pe if snap else None,
        "peg": snap.peg if snap else None,
        "price_to_sales": snap.price_to_sales if snap else None,
    }

    # 분기 데이터 (quarterly_financials 테이블)
    q_rows = repo.get_quarterly_financials(upper, n=16)
    quarterly_revenue = [
        {"period": r["period"], "value": r["revenue"], "is_estimate": False}
        for r in reversed(q_rows) if r.get("revenue") is not None
    ]
    quarterly_eps = [
        {"period": r["period"], "value": r["eps"], "is_estimate": False}
        for r in reversed(q_rows) if r.get("eps") is not None
    ]
    quarterly_roe = [
        {"period": r["period"], "value": r["roe"], "is_estimate": False}
        for r in reversed(q_rows) if r.get("roe") is not None
    ]

    return {
        "revenue": data["revenue"],
        "eps": data["eps"],
        "roe": data["roe"],
        "latest_report_date": data.get("latest_report_date"),
        "metrics": metrics,
        "quarterly": {
            "revenue": quarterly_revenue,
            "eps": quarterly_eps,
            "roe": quarterly_roe,
        },
    }


def _compute_ema(series: pd.Series, span: int) -> list[dict]:
    ema = series.ewm(span=span, adjust=False).mean()
    return [
        {"date": str(d.date()), "value": round(float(v), 4)}
        for d, v in ema.items()
        if not pd.isna(v)
    ]


def _period_to_date(period: str) -> str:
    """'2025Q1' → '2025-03-31'"""
    _ends = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
    year = period[:4]
    q = period[4:]
    return f"{year}-{_ends.get(q, '12-31')}"


@router.get("/{ticker}/price-chart")
def get_price_chart(
    ticker: str,
    user: CurrentUser = Depends(current_user),
):
    upper = ticker.upper()
    today = date.today()
    start = today - timedelta(days=380)

    df, _ = fetch_ohlcv([upper], start, today)
    if df.empty or (upper, "Close") not in df.columns:
        raise HTTPException(status_code=404, detail=f"{upper} OHLCV 데이터 없음")

    close = df[(upper, "Close")].dropna()

    ohlcv_list = [
        {"date": str(d.date()), "close": round(float(v), 4)}
        for d, v in close.items()
    ]

    quarterly_rows = repo.get_quarterly_financials(upper, n=12)
    quarterly_eps = [
        {
            "period": r["period"],
            "date": _period_to_date(r["period"]),
            "eps": r.get("eps"),
            "is_estimate": False,
        }
        for r in quarterly_rows
        if r.get("eps") is not None
    ]

    return {
        "ohlcv": ohlcv_list,
        "ema": {
            "e5": _compute_ema(close, 5),
            "e20": _compute_ema(close, 20),
            "e60": _compute_ema(close, 60),
        },
        "quarterly_eps": quarterly_eps,
    }
