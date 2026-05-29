import os
import time
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from core.auth.deps import current_user, CurrentUser
from api.models import NewsItem, NewsOut

router = APIRouter(prefix="/api/news", tags=["news"])

# (ticker, limit) → (items, expires_at)
_cache: dict[tuple[str, int], tuple[list, float]] = {}
_TTL = 300.0  # 5분


def _fetch_fmp(ticker: str, limit: int) -> list[NewsItem]:
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key or api_key == "your_fmp_key_here":
        raise HTTPException(status_code=503, detail="FMP_API_KEY not configured")

    cache_key = (ticker.upper(), limit)
    now = time.time()
    if cache_key in _cache:
        items, expires_at = _cache[cache_key]
        if now < expires_at:
            return items

    url = (
        f"https://financialmodelingprep.com/api/v3/stock_news"
        f"?tickers={ticker.upper()}&limit={limit}&apikey={api_key}"
    )
    resp = requests.get(url, timeout=10)
    raw: list[dict] = resp.json() if resp.status_code == 200 else []

    items = [
        NewsItem(
            title=r.get("title", ""),
            published_date=r.get("publishedDate", ""),
            url=r.get("url", ""),
            site=r.get("site", ""),
            image=r.get("image") or None,
        )
        for r in raw
    ]
    _cache[cache_key] = (items, now + _TTL)
    return items


@router.get("", response_model=NewsOut)
def get_news(
    ticker: str = Query(..., description="티커 심볼 (예: AMZN)"),
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(current_user),
) -> NewsOut:
    items = _fetch_fmp(ticker, limit)
    return NewsOut(ticker=ticker.upper(), items=items)
