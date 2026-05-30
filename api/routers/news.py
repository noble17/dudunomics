import time
from fastapi import APIRouter, Depends, Query
from core.auth.deps import current_user, CurrentUser
from api.models import NewsItem, NewsOut
from core.data.yf_session import get_session
from core.data.news_provider import fetch_news as _fetch_news_native

router = APIRouter(prefix="/api/news", tags=["news"])

# (ticker, limit) → (items, expires_at)
_cache: dict[tuple[str, int], tuple[list, float]] = {}
_TTL = 300.0  # 5분


def _native_to_items(raw_list: list[dict], limit: int) -> list[NewsItem]:
    items = []
    for r in raw_list[:limit]:
        items.append(NewsItem(
            title=r.get("title", ""),
            published_date=r.get("published_utc", ""),
            url=r.get("link", ""),
            site=r.get("publisher", ""),
            image=r.get("thumbnail"),
        ))
    return items


def _yf_to_items(raw_list: list, limit: int) -> list[NewsItem]:
    items = []
    for r in raw_list[:limit]:
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
    return items


def _fetch_news(ticker: str, limit: int) -> list[NewsItem]:
    cache_key = (ticker.upper(), limit)
    now = time.time()
    if cache_key in _cache:
        items, expires_at = _cache[cache_key]
        if now < expires_at:
            return items

    # 1차: native RSS provider (Google News → Yahoo RSS)
    native_raw = _fetch_news_native(ticker.upper(), limit)
    if native_raw:
        items = _native_to_items(native_raw, limit)
        _cache[cache_key] = (items, now + _TTL)
        return items

    # 최후 fallback: yfinance
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker.upper(), session=get_session()).news or []
        items = _yf_to_items(raw, limit)
    except Exception:
        items = []

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
