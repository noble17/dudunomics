"""공통 종목 데이터 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.models import TickerHydrateOut, TickerOverviewOut
from core import repository as repo
from core.auth.deps import CurrentUser, current_user
from core.data.ticker_data_service import (
    get_data_status,
    get_fundamentals,
    hydrate_ticker_data,
)

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


def get_ticker_overview(ticker: str, universe: str = "sp500") -> dict:
    ticker = ticker.upper()
    return {
        "ticker": ticker,
        "profile": repo.get_ticker_profile(ticker),
        "fundamentals": get_fundamentals(ticker, universe=universe),
        "status": get_data_status(ticker),
    }


@router.get("/{ticker}/overview", response_model=TickerOverviewOut)
def ticker_overview(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    return get_ticker_overview(ticker, universe=universe)


@router.post("/{ticker}/hydrate", response_model=TickerHydrateOut)
def ticker_hydrate(
    ticker: str,
    scopes: list[str] = Query(default=["ohlcv"]),
    user: CurrentUser = Depends(current_user),
):
    return hydrate_ticker_data(ticker.upper(), scopes=scopes)
