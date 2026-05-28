"""Yahoo Finance 전용 HTTP 세션.

requests-cache (SQLite, 24시간) + requests-ratelimiter (초당 2회)를
조합한 CachedLimiterSession을 yfinance에 주입한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from requests import Session
from requests_cache import CacheMixin
from requests_ratelimiter import LimiterMixin

log = logging.getLogger(__name__)

_CACHE_PATH = str(Path(__file__).parents[2] / "data" / "yahoo_cache")

_session: "CachedLimiterSession | None" = None


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    pass


def get_session() -> CachedLimiterSession:
    global _session
    if _session is None:
        _session = CachedLimiterSession(
            cache_name=_CACHE_PATH,
            expire_after=86400,      # 24시간
            per_second=2,
            allowable_codes=(200,),  # 200 OK만 캐시 — 429/4xx는 재시도
        )
        log.info("[yf_session] 세션 생성 (캐시: %s.sqlite)", _CACHE_PATH)
    return _session


def reset_session() -> None:
    global _session
    _session = None
