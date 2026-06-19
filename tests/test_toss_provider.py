from datetime import date
from unittest.mock import MagicMock, patch
import requests


def _resp(payload: dict, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = payload
    if status_code >= 400:
        m.raise_for_status.side_effect = requests.HTTPError("error", response=m)
    else:
        m.raise_for_status.return_value = None
    return m


def test_token_uses_client_credentials_and_caches(monkeypatch):
    monkeypatch.setenv("TOSS_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSS_CLIENT_SECRET", "secret")

    with patch("core.prices.toss.requests.post", return_value=_resp({
        "access_token": "tok",
        "expires_in": 86400,
        "token_type": "Bearer",
    })) as post:
        from core.prices import toss

        toss._TOKEN = None
        assert toss._get_token() == "tok"
        assert toss._get_token() == "tok"

    assert post.call_count == 1
    assert post.call_args.kwargs["data"]["grant_type"] == "client_credentials"
    assert post.call_args.kwargs["data"]["client_id"] == "cid"


def test_get_current_prices_maps_symbols_and_prices(monkeypatch):
    monkeypatch.setenv("TOSS_CLIENT_ID", "cid")
    monkeypatch.setenv("TOSS_CLIENT_SECRET", "secret")

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": [
                 {"symbol": "005930", "lastPrice": "72000", "currency": "KRW"},
                 {"symbol": "AAPL", "lastPrice": "185.70", "currency": "USD"},
             ]
         })) as get:
        from core.prices.toss import TossPriceProvider

        prices = TossPriceProvider().get_current_prices(["005930.KS", "AAPL"])

    assert prices["005930.KS"].current == 72000
    assert prices["005930.KS"].currency == "KRW"
    assert prices["AAPL"].current == 185.70
    assert get.call_args.kwargs["params"]["symbols"] == "005930,AAPL"


def test_exchange_rate_returns_rate(monkeypatch):
    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": {"baseCurrency": "USD", "quoteCurrency": "KRW", "rate": "1380.5"}
         })) as get:
        from core.prices.toss import fetch_exchange_rate

        assert fetch_exchange_rate("USDKRW") == 1380.5

    assert get.call_args.kwargs["params"]["baseCurrency"] == "USD"
    assert get.call_args.kwargs["params"]["quoteCurrency"] == "KRW"


def test_lookup_uses_toss_stocks(monkeypatch):
    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": [
                 {"symbol": "005930", "name": "삼성전자", "englishName": "SamsungElec", "market": "KOSPI", "currency": "KRW"}
             ]
         })) as get:
        from core.prices.toss import TossPriceProvider

        result = TossPriceProvider().lookup("005930.KS")

    assert result == {
        "ticker": "005930.KS",
        "name": "삼성전자",
        "market": "KOSPI",
        "currency": "KRW",
    }
    assert get.call_args.kwargs["params"]["symbols"] == "005930"


def test_fetch_buying_power_uses_account_header(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": {"currency": "KRW", "cashBuyingPower": "5000000"}
         })) as get:
        from core.prices.toss import fetch_buying_power

        assert fetch_buying_power("KRW") == 5_000_000

    assert get.call_args.kwargs["params"]["currency"] == "KRW"
    assert get.call_args_list[0].kwargs["headers"]["X-Tossinvest-Account"] == "7"


def test_fetch_ohlcv_daily_returns_sorted_dataframe():
    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": {
                 "candles": [
                     {"timestamp": "2026-03-25T09:00:00+09:00", "openPrice": "71600", "highPrice": "72300", "lowPrice": "71500", "closePrice": "72000", "volume": "3521000", "currency": "KRW"},
                     {"timestamp": "2026-03-24T09:00:00+09:00", "openPrice": "71200", "highPrice": "71800", "lowPrice": "71000", "closePrice": "71600", "volume": "2984000", "currency": "KRW"},
                 ],
                 "nextBefore": None,
             }
         })):
        from core.prices.toss import fetch_ohlcv_daily

        df = fetch_ohlcv_daily("005930.KS", date(2026, 3, 1), date(2026, 3, 31))

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index.is_monotonic_increasing
    assert float(df.iloc[-1]["Close"]) == 72000


def test_fetch_holdings_maps_to_internal_holding_shape(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": {
                 "items": [
                     {"symbol": "005930", "name": "삼성전자", "marketCountry": "KR", "currency": "KRW", "quantity": "100", "averagePurchasePrice": "65000"},
                     {"symbol": "AAPL", "name": "Apple Inc.", "marketCountry": "US", "currency": "USD", "quantity": "10", "averagePurchasePrice": "155.3"},
                 ]
             }
         })) as get:
        from core.prices.toss import fetch_holdings

        holdings = fetch_holdings()

    assert holdings[0] == {
        "ticker": "005930.KS",
        "name": "삼성전자",
        "quantity": 100.0,
        "avg_price": 65000.0,
        "currency": "KRW",
        "market": "KRX",
        "sector": None,
    }
    assert holdings[1]["ticker"] == "AAPL"
    assert holdings[1]["market"] == "NASDAQ"
    assert get.call_args_list[0].kwargs["headers"]["X-Tossinvest-Account"] == "7"


def test_fetch_holdings_enriches_market_without_sector(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")

    holdings_resp = _resp({
        "result": {
            "items": [
                {"symbol": "0195R0", "name": "TIGER 삼성전자단일종목레버리지", "marketCountry": "KR", "currency": "KRW", "quantity": "800", "averagePurchasePrice": "25345"},
            ]
        }
    })
    stocks_resp = _resp({
        "result": [
            {"symbol": "0195R0", "name": "TIGER 삼성전자단일종목레버리지", "market": "KOSPI", "securityType": "ETF", "currency": "KRW", "leverageFactor": "2"}
        ]
    })

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", side_effect=[holdings_resp, stocks_resp]):
        from core.prices.toss import fetch_holdings

        holdings = fetch_holdings()

    assert holdings[0]["ticker"] == "0195R0"
    assert holdings[0]["market"] == "KOSPI"
    assert holdings[0]["sector"] is None


def test_fetch_holdings_refreshes_token_once_on_401(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")

    unauthorized = _resp({"error": {"code": "expired-token"}}, status_code=401)
    ok = _resp({"result": {"items": []}})

    with patch("core.prices.toss._get_token", side_effect=["old", "new"]) as token, \
         patch("core.prices.toss.requests.get", side_effect=[unauthorized, ok]) as get:
        from core.prices.toss import fetch_holdings

        assert fetch_holdings() == []

    assert token.call_count == 2
    assert get.call_count == 2
    assert get.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer old"
    assert get.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer new"


def test_fetch_orders_maps_filled_orders_to_trades(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", return_value=_resp({
             "result": {
                 "items": [
                     {
                         "orderId": "ord-1",
                         "symbol": "005930",
                         "side": "BUY",
                         "status": "FILLED",
                         "currency": "KRW",
                         "marketCountry": "KR",
                         "market": "KOSPI",
                         "executedAt": "2026-06-05T10:03:00+09:00",
                         "execution": {
                             "filledQuantity": "3",
                             "averageFilledPrice": "72000",
                             "commission": "12",
                             "filledAt": "2026-06-05T10:03:00+09:00",
                         },
                     },
                     {
                         "orderId": "ord-2",
                         "symbol": "AAPL",
                         "side": "BUY",
                         "status": "PENDING",
                         "quantity": "2",
                         "price": "190",
                     },
                 ]
             }
         })) as get:
        from core.prices.toss import fetch_orders

        trades = fetch_orders(start_date="2026-06-01", end_date="2026-06-07")

    assert trades == [{
        "external_id": "ord-1",
        "ticker": "005930.KS",
        "market": "KOSPI",
        "trade_type": "BUY",
        "quantity": 3.0,
        "price": 72000.0,
        "currency": "KRW",
        "traded_at": "2026-06-05",
        "fee": 12.0,
        "note": "Toss OpenAPI 주문/체결 동기화",
    }]
    assert get.call_args.kwargs["params"] == {"status": "OPEN", "from": "2026-06-01", "to": "2026-06-07"}
    assert get.call_args.kwargs["headers"]["X-Tossinvest-Account"] == "7"


def test_fetch_closed_orders_follows_pagination_and_includes_tax(monkeypatch):
    monkeypatch.setenv("TOSS_ACCOUNT_SEQ", "7")
    first = _resp({
        "result": {
            "orders": [{
                "orderId": "sell-1",
                "symbol": "AAPL",
                "side": "SELL",
                "status": "FILLED",
                "currency": "USD",
                "marketCountry": "US",
                "execution": {
                    "filledQuantity": "2",
                    "averageFilledPrice": "210",
                    "commission": "1.2",
                    "tax": "0.3",
                    "filledAt": "2026-06-18T10:00:00+09:00",
                },
            }],
            "hasNext": True,
            "nextCursor": "next-1",
        }
    })
    second = _resp({
        "result": {
            "orders": [],
            "hasNext": False,
            "nextCursor": None,
        }
    })

    with patch("core.prices.toss._get_token", return_value="tok"), \
         patch("core.prices.toss.requests.get", side_effect=[first, second]) as get:
        from core.prices.toss import fetch_orders

        trades = fetch_orders(status="CLOSED")

    assert trades[0]["trade_type"] == "SELL"
    assert trades[0]["fee"] == 1.5
    assert get.call_args_list[0].kwargs["params"] == {"status": "CLOSED", "limit": 100}
    assert get.call_args_list[1].kwargs["params"] == {
        "status": "CLOSED",
        "limit": 100,
        "cursor": "next-1",
    }
