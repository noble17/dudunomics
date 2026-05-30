# tests/test_rebalancing_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def reb_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app

    mock_price = MagicMock()
    mock_price.current = 100.0
    mock_price.currency = "USD"

    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_pp.get_current_prices.return_value = {
            "AAPL": mock_price, "MSFT": mock_price
        }
        c = TestClient(app)
        c.post("/api/auth/signup", json={"email": "reb@test.com", "password": "password123"})
        c.put("/api/holdings/AAPL", json={
            "name": "Apple", "currency": "USD", "quantity": 10, "avg_price": 180.0
        })
        c.put("/api/holdings/MSFT", json={
            "name": "Microsoft", "currency": "USD", "quantity": 5, "avg_price": 400.0
        })
        yield c


def test_rebalancing_empty_without_target(reb_client):
    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_price = MagicMock()
        mock_price.current = 100.0
        mock_price.currency = "USD"
        mock_pp.get_current_prices.return_value = {"AAPL": mock_price, "MSFT": mock_price}
        res = reb_client.get("/api/portfolio/rebalancing")
    assert res.status_code == 200
    data = res.json()
    assert all(r["action"] == "NO_TARGET" for r in data)


def test_patch_target_weight(reb_client):
    res = reb_client.patch("/api/holdings/AAPL", json={"target_weight": 60.0})
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_patch_target_weight_over_100_warns(reb_client):
    reb_client.patch("/api/holdings/AAPL", json={"target_weight": 70.0})
    res = reb_client.patch("/api/holdings/MSFT", json={"target_weight": 60.0})
    assert res.status_code == 200
    assert res.json()["over_100"] is True


def test_rebalancing_action_buy_sell(reb_client):
    reb_client.patch("/api/holdings/AAPL", json={"target_weight": 30.0})
    with patch("api.routers.portfolio._price_provider") as mock_pp, \
         patch("api.routers.portfolio._get_usdkrw", return_value=1350.0):
        mock_price = MagicMock()
        mock_price.current = 100.0
        mock_price.currency = "USD"
        mock_pp.get_current_prices.return_value = {"AAPL": mock_price, "MSFT": mock_price}
        res = reb_client.get("/api/portfolio/rebalancing")
    assert res.status_code == 200


def test_patch_nonexistent_ticker(reb_client):
    res = reb_client.patch("/api/holdings/ZZZZ", json={"target_weight": 50.0})
    assert res.status_code == 404
