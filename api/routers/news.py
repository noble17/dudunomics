import time
import yfinance as yf
from fastapi import APIRouter, Depends, Query
from core.auth.deps import current_user, CurrentUser
from api.models import NewsItem, NewsOut

router = APIRouter(prefix="/api/news", tags=["news"])

# (ticker, limit) → (items, expires_at)
_cache: dict[tuple[str, int], tuple[list, float]] = {}
_TTL = 300.0  # 5분


def _fetch_news(ticker: str, limit: int) -> list[NewsItem]:
    cache_key = (ticker.upper(), limit)
    now = time.time()
    if cache_key in _cache:
        items, expires_at = _cache[cache_key]
        if now < expires_at:
            return items

    raw = yf.Ticker(ticker.upper()).news or []

    items = []
    for r in raw[:limit]:
        c = r.get("content", {})
        canonical = c.get("canonicalUrl", {}) or {}
        provider = c.get("provider", {}) or {}
        thumbnail = c.get("thumbnail", {}) or {}
        resolutions = thumbnail.get("resolutions", [])
        image = resolutions[0].get("url") if resolutions else thumbnail.get("originalUrl")
        items.append(NewsItem(
            title=c.get("title", r.get("title", "")),
            published_date=c.get("pubDate", ""),
            url=canonical.get("url", ""),
            site=provider.get("displayName", "Yahoo Finance"),
            image=image or None,
        ))

    _cache[cache_key] = (items, now + _TTL)
    return items


@router.get("", response_model=NewsOut)
def get_news(
    ticker: str = Query(..., description="티커 심볼 (예: AMZN)"),
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(current_user),
) -> NewsOut:
    items = _fetch_news(ticker, limit)
    return NewsOut(ticker=ticker.upper(), items=items)
