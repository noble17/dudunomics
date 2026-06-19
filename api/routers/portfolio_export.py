import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, status

from api.models import PortfolioExportOut
import core.repository as repo

router = APIRouter(prefix="/api/external", tags=["external"])


def _export_user_id(authorization: str | None) -> int:
    api_key = os.getenv("PORTFOLIO_EXPORT_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="포트폴리오 export API가 설정되지 않았습니다.",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 API Key가 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_ids = repo.get_active_user_ids()
    if not user_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="export 대상 사용자를 찾을 수 없습니다.",
        )
    if len(user_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="활성 사용자가 여러 명이라 export 대상을 결정할 수 없습니다.",
        )
    return user_ids[0]


def _sheet_ticker(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return upper[:-3]
    return upper


def _sheet_market(market: str | None, ticker: str) -> str:
    value = (market or "").upper()
    if value in ("KRX", "KOSPI"):
        return "KOSPI"
    if value == "KOSDAQ":
        return "KOSDAQ"
    if value == "AMEX":
        return "AMS"
    if value:
        return value
    if ticker.upper().endswith(".KS"):
        return "KOSPI"
    if ticker.upper().endswith(".KQ"):
        return "KOSDAQ"
    return "NASDAQ"


def _row(holding: dict, number: int) -> dict:
    return {
        "no": number,
        "name": holding["name"],
        "ticker": _sheet_ticker(holding["ticker"]),
        "market": _sheet_market(holding.get("market"), holding["ticker"]),
        "quantity": holding["quantity"],
        "avg_price": holding["avg_price"],
        "sector": holding.get("sector") or "",
    }


@router.get("/portfolio", response_model=PortfolioExportOut)
def export_portfolio(authorization: str | None = Header(default=None)):
    user_id = _export_user_id(authorization)
    holdings = repo.get_holdings(user_id)
    cash = repo.get_cash_total(user_id)

    domestic_holdings = sorted(
        (holding for holding in holdings if holding["currency"] == "KRW"),
        key=lambda holding: holding["ticker"],
    )
    overseas_holdings = sorted(
        (holding for holding in holdings if holding["currency"] == "USD"),
        key=lambda holding: holding["ticker"],
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "cash": {
            "krw": cash["cash_krw"],
            "usd": cash["cash_usd"],
        },
        "domestic": [
            _row(holding, number)
            for number, holding in enumerate(domestic_holdings, start=1)
        ],
        "overseas": [
            _row(holding, number)
            for number, holding in enumerate(overseas_holdings, start=21)
        ],
    }
