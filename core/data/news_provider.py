"""
News provider: Google News RSS (primary) → Yahoo Finance RSS (fallback).
In-memory cache with 5-minute TTL.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import feedparser
import httpx

log = logging.getLogger(__name__)

_CLIENT = httpx.Client(
    timeout=10,
    follow_redirects=True,
    headers={"User-Agent": "dudunomics/1.0"},
)
_CACHE: dict[str, tuple[list[dict], float]] = {}
_TTL = 300.0  # 5 min


def _google_news(ticker: str, limit: int) -> list[dict]:
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        r = _CLIENT.get(url)
        feed = feedparser.parse(r.text)
        items = []
        for entry in feed.entries[:limit]:
            source = entry.get("source", {})
            publisher = source.get("title", "Google News") if isinstance(source, dict) else "Google News"
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "publisher": publisher,
                "published_utc": entry.get("published", ""),
                "thumbnail": None,
                "uuid": hashlib.md5(entry.get("link", "").encode()).hexdigest(),
            })
        return items
    except Exception as e:
        log.debug("google news failed for %s: %s", ticker, e)
        return []


def _yahoo_rss(ticker: str, limit: int) -> list[dict]:
    try:
        url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
        r = _CLIENT.get(url)
        feed = feedparser.parse(r.text)
        items = []
        for entry in feed.entries[:limit]:
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "publisher": "Yahoo Finance",
                "published_utc": entry.get("published", ""),
                "thumbnail": None,
                "uuid": hashlib.md5(entry.get("link", "").encode()).hexdigest(),
            })
        return items
    except Exception as e:
        log.debug("yahoo rss failed for %s: %s", ticker, e)
        return []


def fetch_news(ticker: str, limit: int = 10) -> list[dict]:
    """Fetch news from Google RSS → Yahoo RSS fallback. Returns raw dicts."""
    key = f"{ticker.upper()}:{limit}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached[1] < _TTL:
        return cached[0]
    items = _google_news(ticker, limit)
    if not items:
        items = _yahoo_rss(ticker, limit)
    _CACHE[key] = (items, time.time())
    return items
