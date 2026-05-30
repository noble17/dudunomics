import pytest
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


def test_portfolio_history_empty(client):
    res = client.get("/api/portfolio/history")
    assert res.status_code == 200
    assert res.json() == []
