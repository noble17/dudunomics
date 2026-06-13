import pytest
from datetime import datetime
from unittest.mock import patch
from core.prices.base import Price
import core.repository as repo


def test_portfolio_empty(client):
    res = client.get("/api/portfolio/current")
    assert res.status_code == 200
    data = res.json()
    assert data["rows"] == []
    assert data["total_equity_krw"] == 0


def test_portfolio_with_holdings(client):
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    repo.upsert_holding(uid, "005930.KS", "삼성전자", "KRW", 10, 70000)
    repo.upsert_holding(uid, "AAPL", "Apple", "USD", 5, 175.0)

    mock_prices = {
        "005930.KS": Price(ticker="005930.KS", current=75000, currency="KRW"),
        "AAPL": Price(ticker="AAPL", current=180.0, currency="USD"),
    }
    with patch("api.routers.portfolio._price_provider.get_current_prices", return_value=mock_prices), \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        res = client.get("/api/portfolio/current")

    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 2
    assert data["total_equity_krw"] > 0

    krw_row = next(r for r in data["rows"] if r["ticker"] == "005930.KS")
    assert krw_row["market_value_krw"] == 750000
    assert krw_row["return_pct"] == pytest.approx((75000 - 70000) / 70000 * 100, rel=1e-3)


def test_portfolio_keeps_holding_when_quote_missing(client):
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    repo.upsert_holding(uid, "0195R0.KS", "삼성전자 2X", "KRW", 800, 25345, market="KRX")

    with patch("api.routers.portfolio._price_provider.get_current_prices", return_value={}), \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        res = client.get("/api/portfolio/current")

    assert res.status_code == 200
    data = res.json()
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["ticker"] == "0195R0.KS"
    assert row["current_price"] == 25345
    assert row["return_pct"] == 0


def test_portfolio_row_includes_saved_market(client):
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    repo.upsert_holding(uid, "0195R0", "TIGER 삼성전자단일종목레버리지", "KRW", 800, 25345, sector="ETF 2x", market="KOSPI")

    with patch("api.routers.portfolio._price_provider.get_current_prices", return_value={}), \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        res = client.get("/api/portfolio/current")

    row = res.json()["rows"][0]
    assert row["market"] == "KOSPI"
    assert row["sector"] == "ETF 2x"


def test_portfolio_history_empty(client):
    res = client.get("/api/portfolio/history")
    assert res.status_code == 200
    assert res.json() == []


def test_portfolio_history_supports_rollup_bucket(client):
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    repo.insert_snapshot(uid, datetime(2026, 6, 7, 9, 3), 100, 150, 50, 1, 1.5, 0.5, 1000, [])
    repo.insert_snapshot(uid, datetime(2026, 6, 7, 9, 11), 110, 170, 60, 1.1, 1.7, 0.6, 1000, [])
    repo.refresh_snapshot_rollups(user_id=uid, buckets=("10m", "1h", "1w"))

    res = client.get("/api/portfolio/history?bucket=10m&limit=10")
    assert res.status_code == 200
    assert [row["total_with_cash_krw"] for row in res.json()] == [170, 150]

    hourly = client.get("/api/portfolio/history?bucket=1h&limit=10").json()
    assert len(hourly) == 1
    assert hourly[0]["total_with_cash_krw"] == 170

    weekly = client.get("/api/portfolio/history?bucket=1w&limit=10").json()
    assert len(weekly) == 1
    assert weekly[0]["total_with_cash_krw"] == 170


def test_portfolio_analytics_returns_holding_performance(client):
    user = repo.get_user_by_email("test@test.com")
    uid = user["id"]
    repo.upsert_holding(uid, "AAPL", "Apple", "USD", 5, 175.0)

    rows = [{
        "ticker": "AAPL",
        "name": "Apple",
        "price": 180.0,
        "change_pct": 1.2,
        "volume": 1_000_000,
        "avg_volume20": 900_000,
        "perf_1w": 2.5,
        "perf_1m": 6.0,
        "perf_6m": 18.0,
        "perf_ytd": 25.0,
        "ma20": 170.0,
        "ma50": 160.0,
        "ma200": 140.0,
        "price_vs_ma20": 5.88,
        "price_vs_ma50": 12.5,
        "price_vs_ma200": 28.57,
        "day_low": 178.0,
        "day_high": 182.0,
        "range_52w_low": 120.0,
        "range_52w_high": 190.0,
    }]

    with patch("api.routers.portfolio.build_ticker_performance", return_value=rows) as build:
        res = client.get("/api/portfolio/analytics")

    assert res.status_code == 200
    assert res.json()[0]["ticker"] == "AAPL"
    assert res.json()[0]["quantity"] == 5
    assert res.json()[0]["avg_price"] == 175.0
    assert res.json()[0]["price_vs_ma20"] == 5.88
    build.assert_called_once()
