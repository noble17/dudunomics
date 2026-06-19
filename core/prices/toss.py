"""Toss Invest OpenAPI provider.

DB/UI ticker는 기존 yfinance 형식을 유지하고, Toss 호출 직전에만 symbol로 변환한다.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime

import pandas as pd
import requests

from core.ids import is_domestic, to_yf
from core.prices.base import Price, PriceProvider

TOSS_BASE = "https://openapi.tossinvest.com"
_TOKEN: tuple[str, float] | None = None


def _to_toss_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return t[:-3]
    return t


def _to_internal_ticker(symbol: str, market_country: str | None = None) -> str:
    s = symbol.strip().upper()
    if market_country == "KR" or (s.isdigit() and len(s) == 6):
        return to_yf(s)
    return s


def _first_value(row: dict, keys: tuple[str, ...], default=None):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _order_value(row: dict, keys: tuple[str, ...], default=None):
    execution = row.get("execution") if isinstance(row.get("execution"), dict) else {}
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
        value = execution.get(key)
        if value not in (None, ""):
            return value
    return default


def _date_part(value) -> str:
    if not value:
        return date.today().isoformat()
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _get_token() -> str | None:
    global _TOKEN
    now = time.time()
    if _TOKEN and _TOKEN[1] > now:
        return _TOKEN[0]

    client_id = os.getenv("TOSS_CLIENT_ID", "")
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None

    res = requests.post(
        f"{TOSS_BASE}/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    token = data.get("access_token")
    if not token:
        return None
    ttl = int(data.get("expires_in") or 3600)
    _TOKEN = (token, now + max(ttl - 60, 60))
    return token


def _headers(token: str, *, account: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if account:
        account_seq = os.getenv("TOSS_ACCOUNT_SEQ", "")
        if not account_seq:
            raise RuntimeError("TOSS_ACCOUNT_SEQ 환경변수가 필요합니다.")
        headers["X-Tossinvest-Account"] = account_seq
    return headers


def _get(path: str, *, params: dict | None = None, account: bool = False) -> requests.Response:
    global _TOKEN
    token = _get_token()
    if not token:
        raise RuntimeError("Toss 토큰 없음")

    res = requests.get(
        f"{TOSS_BASE}{path}",
        params=params,
        headers=_headers(token, account=account),
        timeout=10,
    )
    if res.status_code == 401:
        _TOKEN = None
        token = _get_token()
        if not token:
            raise RuntimeError("Toss 토큰 없음")
        res = requests.get(
            f"{TOSS_BASE}{path}",
            params=params,
            headers=_headers(token, account=account),
            timeout=10,
        )
    res.raise_for_status()
    return res


class TossPriceProvider(PriceProvider):
    def get_current_price(self, ticker: str) -> Price:
        prices = self.get_current_prices([ticker])
        if ticker.upper() in prices:
            return prices[ticker.upper()]
        raise RuntimeError(f"Toss 시세 조회 실패: {ticker}")

    def get_current_prices(
        self,
        tickers: list[str],
        markets: dict[str, str | None] | None = None,
    ) -> dict[str, Price]:
        if not tickers:
            return {}

        normalized = [t.strip().upper() for t in tickers]
        symbol_to_ticker = {_to_toss_symbol(t): t for t in normalized}
        try:
            res = _get(
                "/api/v1/prices",
                params={"symbols": ",".join(symbol_to_ticker)},
            )
        except RuntimeError:
            return {}

        result: dict[str, Price] = {}
        for row in res.json().get("result") or []:
            symbol = row.get("symbol", "")
            ticker = symbol_to_ticker.get(symbol)
            if not ticker:
                continue
            result[ticker] = Price(
                ticker=ticker,
                current=float(row.get("lastPrice") or 0),
                currency=row.get("currency") or ("KRW" if is_domestic(ticker) else "USD"),
                change_pct=None,
            )
        return result

    def lookup(self, ticker: str, market: str | None = None) -> dict | None:
        """Toss stocks API로 심볼 기본 정보를 조회한다."""
        symbol = _to_toss_symbol(ticker)
        rows = _fetch_stock_infos([symbol])
        info = rows.get(symbol.upper())
        if not info:
            return None
        market_country = "KR" if (info.get("currency") == "KRW" or str(info.get("market", "")).upper().startswith("KOS")) else None
        return {
            "ticker": _to_internal_ticker(str(info.get("symbol") or symbol), market_country),
            "name": info.get("name") or info.get("englishName") or ticker,
            "market": info.get("market") or market or ("KRX" if market_country == "KR" else "NASDAQ"),
            "currency": info.get("currency") or ("KRW" if market_country == "KR" else "USD"),
        }


def fetch_exchange_rate(pair: str = "USDKRW") -> float:
    p = pair.upper()
    if len(p) != 6:
        raise ValueError(f"Toss 환율 pair 미지원: {pair}")
    res = _get(
        "/api/v1/exchange-rate",
        params={"baseCurrency": p[:3], "quoteCurrency": p[3:]},
    )
    return float((res.json().get("result") or {}).get("rate") or 0)


def fetch_buying_power(currency: str) -> float:
    c = currency.upper()
    if c not in ("KRW", "USD"):
        raise ValueError(f"Toss 매수 가능 금액 통화 미지원: {currency}")
    res = _get(
        "/api/v1/buying-power",
        params={"currency": c},
        account=True,
    )
    return float((res.json().get("result") or {}).get("cashBuyingPower") or 0)


def _fetch_stock_infos(symbols: list[str]) -> dict[str, dict]:
    if not symbols:
        return {}
    try:
        res = _get(
            "/api/v1/stocks",
            params={"symbols": ",".join(symbols[:200])},
        )
    except Exception:
        return {}
    rows = res.json().get("result") or []
    if not isinstance(rows, list):
        return {}
    return {str(row.get("symbol", "")).upper(): row for row in rows if row.get("symbol")}


def _ohlcv_count(start: date, end: date) -> int:
    """요청 구간을 덮을 만큼 일봉 count를 넉넉히 계산한다."""
    requested_days = max((end - start).days + 10, 200)
    max_count = int(os.getenv("TOSS_OHLCV_MAX_COUNT", "1200") or 1200)
    return min(requested_days, max(max_count, 200))


def fetch_ohlcv_daily(ticker: str, start: date, end: date) -> pd.DataFrame:
    params = {
        "symbol": _to_toss_symbol(ticker),
        "interval": "1d",
        "count": _ohlcv_count(start, end),
        "adjusted": "true",
    }
    try:
        res = _get("/api/v1/candles", params=params)
    except requests.HTTPError:
        if params["count"] == 200:
            return pd.DataFrame()
        params["count"] = 200
        try:
            res = _get("/api/v1/candles", params=params)
        except (RuntimeError, requests.HTTPError):
            return pd.DataFrame()
    except RuntimeError:
        return pd.DataFrame()

    rows = []
    for row in (res.json().get("result") or {}).get("candles") or []:
        ts = pd.to_datetime(row.get("timestamp")).tz_localize(None)
        dt = ts.date()
        if dt < start or dt > end:
            continue
        rows.append({
            "date": dt,
            "Open": float(row.get("openPrice") or 0),
            "High": float(row.get("highPrice") or 0),
            "Low": float(row.get("lowPrice") or 0),
            "Close": float(row.get("closePrice") or 0),
            "Volume": int(float(row.get("volume") or 0)),
        })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date")
    df.index = pd.to_datetime(df.pop("date"))
    return df


def fetch_holdings(symbol: str | None = None) -> list[dict]:
    params = {"symbol": _to_toss_symbol(symbol)} if symbol else None
    res = _get(
        "/api/v1/holdings",
        params=params,
        account=True,
    )

    items = (res.json().get("result") or {}).get("items") or []
    stock_infos = _fetch_stock_infos([
        str(item.get("symbol", "")).upper()
        for item in items
        if item.get("symbol")
    ])

    holdings = []
    for item in items:
        qty = float(item.get("quantity") or 0)
        if qty <= 0:
            continue
        market_country = item.get("marketCountry")
        symbol = str(item.get("symbol", "")).upper()
        stock_info = stock_infos.get(symbol, {})
        holdings.append({
            "ticker": _to_internal_ticker(symbol, market_country),
            "name": stock_info.get("name") or item.get("name") or symbol,
            "quantity": qty,
            "avg_price": float(item.get("averagePurchasePrice") or 0),
            "currency": stock_info.get("currency") or item.get("currency") or ("KRW" if market_country == "KR" else "USD"),
            "market": stock_info.get("market") or ("KRX" if market_country == "KR" else "NASDAQ"),
            "sector": None,
        })
    return holdings


def fetch_orders(start_date: str | None = None, end_date: str | None = None, status: str = "OPEN") -> list[dict]:
    """Toss 주문/체결 목록을 내부 거래 로그 형태로 정규화한다.

    주문 API 응답은 OpenAPI 버전별로 체결 수량/평균가 필드명이 다를 수 있어
    대표 후보 필드를 순서대로 읽는다. 미체결 주문은 거래 기록에 넣지 않는다.
    """
    params = {"status": status}
    if start_date:
        params["from"] = start_date
    if end_date:
        params["to"] = end_date

    items = []
    cursor = None
    while True:
        page_params = dict(params)
        if status == "CLOSED":
            page_params["limit"] = 100
            if cursor:
                page_params["cursor"] = cursor
        res = _get(
            "/api/v1/orders",
            params=page_params,
            account=True,
        )
        result = res.json().get("result") or {}
        if isinstance(result, list):
            items.extend(result)
            break
        items.extend(result.get("orders") or result.get("items") or [])
        if status != "CLOSED" or not result.get("hasNext") or not result.get("nextCursor"):
            break
        cursor = result["nextCursor"]

    trades = []
    for row in items:
        side = str(_first_value(row, ("side", "orderSide", "tradeType"), "")).upper()
        if side not in ("BUY", "SELL"):
            continue

        raw_status = str(_first_value(row, ("status", "orderStatus", "state"), "")).upper()
        if raw_status and raw_status not in (
            "FILLED", "EXECUTED", "COMPLETED", "DONE",
            "PARTIAL_FILLED", "PARTIALLY_FILLED", "CANCELED", "REJECTED", "REPLACED",
        ):
            continue

        qty = float(_order_value(row, ("executedQuantity", "filledQuantity", "filledQty"), 0) or 0)
        price = float(_order_value(row, ("averageExecutedPrice", "averageFilledPrice", "avgExecutionPrice", "filledAveragePrice"), 0) or 0)
        if qty <= 0 or price <= 0:
            continue

        symbol = str(_first_value(row, ("symbol", "ticker"), "")).upper()
        if not symbol:
            continue

        market_country = _first_value(row, ("marketCountry", "country"), None)
        external_id = str(_first_value(row, ("orderId", "id", "orderNo", "orderNumber"), ""))
        executed_at = _order_value(row, ("executedAt", "filledAt", "updatedAt", "createdAt", "orderedAt"), None)

        trades.append({
            "external_id": external_id or f"{symbol}:{side}:{_date_part(executed_at)}:{qty}:{price}",
            "ticker": _to_internal_ticker(symbol, market_country),
            "market": _first_value(row, ("market", "exchange"), None) or ("KRX" if market_country == "KR" else "NASDAQ"),
            "trade_type": side,
            "quantity": qty,
            "price": price,
            "currency": _first_value(row, ("currency",), None) or ("KRW" if market_country == "KR" else "USD"),
            "traded_at": _date_part(executed_at),
            "fee": (
                float(_order_value(row, ("fee", "commission", "commissionAmount"), 0) or 0)
                + float(_order_value(row, ("tax", "taxAmount"), 0) or 0)
            ),
            "note": "Toss OpenAPI 주문/체결 동기화",
        })
    return trades
