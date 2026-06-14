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


def _prefer_choice(choice_metrics: dict, key: str, fallback):
    value = choice_metrics.get(key)
    return value if value is not None else fallback


@router.get("/{ticker}/financials")
def get_financials(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    upper = ticker.upper()
    include_choice = repo.is_user_watchlist_ticker(user.id, upper)
    data = fetch_annual_financials(upper, include_choicestock=include_choice)
    if data is None:
        raise HTTPException(status_code=404, detail=f"{upper} 재무 데이터 없음 (국내 종목 미지원)")

    snap = fetch_fundamentals(upper)
    choice = data.get("choicestock") or {}
    choice_metrics = choice.get("metrics") or {}
    metrics: dict = {
        "market_cap_m": _prefer_choice(choice_metrics, "market_cap_m", snap.market_cap_m if snap else None),
        "trailing_pe": _prefer_choice(choice_metrics, "trailing_pe", snap.trailing_pe if snap else None),
        "forward_pe": _prefer_choice(choice_metrics, "forward_pe", snap.forward_pe if snap else None),
        "forward_eps": snap.forward_eps if snap else None,
        "peg": _prefer_choice(choice_metrics, "peg", snap.peg if snap else None),
        "price_to_sales": _prefer_choice(choice_metrics, "price_to_sales", snap.price_to_sales if snap else None),
        "source": choice_metrics.get("source") or choice.get("source"),
        "source_url": choice.get("source_url"),
        "as_of": choice_metrics.get("as_of") or choice.get("as_of"),
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
        "sources": {
            "choicestock": {
                "source": choice.get("source"),
                "source_url": choice.get("source_url"),
                "as_of": choice.get("as_of"),
            }
        },
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
    start = today - timedelta(days=1100)

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
            "e120": _compute_ema(close, 120),
        },
        "quarterly_eps": quarterly_eps,
    }
