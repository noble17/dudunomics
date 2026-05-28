"""Upbit 공개 REST API — BTC/KRW 현재가 조회 (API 키 불필요)."""
import requests
from core.prices.base import Price


class UpbitProvider:
    _BASE = "https://api.upbit.com/v1"

    def get_btc_krw(self) -> Price:
        res = requests.get(
            f"{self._BASE}/ticker",
            params={"markets": "KRW-BTC"},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()[0]
        current = float(data["trade_price"])
        change_pct = float(data["signed_change_rate"]) * 100
        return Price(
            ticker="BTC",
            current=current,
            currency="KRW",
            change_pct=change_pct,
        )
