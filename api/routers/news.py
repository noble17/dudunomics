import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fastapi import APIRouter, Depends, Query
from core.auth.deps import current_user, CurrentUser
from api.models import NewsItem, NewsOut
from core.data.yf_session import get_session
from core.data.news_provider import fetch_news as _fetch_news_native
from core.data.news_provider import filter_recent_news
from core.data.choicestock_public import get_public_summary
import core.repository as repo

router = APIRouter(prefix="/api/news", tags=["news"])

# (ticker, limit, include_choicestock) → (items, expires_at)
_cache: dict[tuple[str, int, bool], tuple[list, float]] = {}
_TTL = 300.0  # 5분


def _recent_items(items: list[NewsItem], days: int = 7) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent: list[NewsItem] = []
    for item in items:
        try:
            dt = parsedate_to_datetime(item.published_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt >= cutoff:
            recent.append(item)
    return recent


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
    return _recent_items(items, days=7)[:limit]


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


def _choicestock_to_items(ticker: str, limit: int) -> list[NewsItem]:
    summary = get_public_summary(ticker)
    if not summary:
        return []
    items = []
    for row in (summary.get("news") or [])[:limit]:
        items.append(NewsItem(
            title=row.get("title", ""),
            published_date=row.get("published_date") or "",
            url=row.get("url", ""),
            site=row.get("site", "ChoiceStock public page"),
            image=None,
        ))
    return items


def _dedupe_news(items: list[NewsItem], limit: int) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        key = item.url or item.title
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _fetch_news(ticker: str, limit: int, include_choicestock: bool = False) -> list[NewsItem]:
    cache_key = (ticker.upper(), limit, include_choicestock)
    now = time.time()
    if cache_key in _cache:
        items, expires_at = _cache[cache_key]
        if now < expires_at:
            return items

    choice_items = _choicestock_to_items(ticker, limit) if include_choicestock else []

    # 1차: native RSS provider (Google News → Yahoo RSS)
    native_raw = filter_recent_news(_fetch_news_native(ticker.upper(), limit * 3), days=7)
    if native_raw:
        items = _native_to_items(native_raw, limit)
        merged = _dedupe_news(choice_items + items, limit)
        _cache[cache_key] = (merged, now + _TTL)
        return merged

    # 최후 fallback: yfinance
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker.upper(), session=get_session()).news or []
        items = _yf_to_items(raw, limit)
    except Exception:
        items = []

    merged = _dedupe_news(choice_items + items, limit)
    _cache[cache_key] = (merged, now + _TTL)
    return merged


@router.get("", response_model=NewsOut)
def get_news(
    ticker: str = Query(..., description="티커 심볼 (예: AMZN)"),
    limit: int = Query(10, ge=1, le=50),
    user: CurrentUser = Depends(current_user),
) -> NewsOut:
    include_choice = repo.is_user_watchlist_ticker(user.id, ticker.upper())
    items = _fetch_news(ticker, limit, include_choicestock=include_choice)
    return NewsOut(ticker=ticker.upper(), items=items)
