"""Market data provider selection helpers."""
from __future__ import annotations

import os


def prefer_toss_market_data() -> bool:
    provider = os.getenv("MARKET_DATA_PROVIDER", "").lower()
    if provider == "kis":
        return False
    if provider == "toss":
        return True
    return bool(os.getenv("TOSS_CLIENT_ID") and os.getenv("TOSS_CLIENT_SECRET"))
