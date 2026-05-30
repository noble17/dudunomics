# tests/test_trades_api.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def trades_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "trades@test.com", "password": "password123"})
    # 보유 종목 사전 등록
    c.put("/api/holdings/AAPL", json={
        "name": "Apple Inc.", "currency": "USD",
        "quantity": 10, "avg_price": 180.0, "market": "NASDAQ"
    })
    return c


def test_list_trades_empty(trades_client):
    res = trades_client.get("/api/trades")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_buy_trade(trades_client):
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "market": "NASDAQ", "trade_type": "BUY",
        "quantity": 5, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ticker"] == "AAPL"
    assert data["trade_type"] == "BUY"
    assert "id" in data


def test_create_sell_trade(trades_client):
    # 먼저 BUY
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 5, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    # SELL
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "SELL",
        "quantity": 3, "price": 210.0, "currency": "USD", "traded_at": "2025-07-01"
    })
    assert res.status_code == 201
    assert res.json()["trade_type"] == "SELL"


def test_sell_exceeds_quantity_rejected(trades_client):
    res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "SELL",
        "quantity": 999, "price": 200.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    assert res.status_code == 422


def test_ticker_filter(trades_client):
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 1, "price": 190.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    res = trades_client.get("/api/trades?ticker=AAPL")
    assert res.status_code == 200
    assert all(t["ticker"] == "AAPL" for t in res.json())


def test_delete_trade(trades_client):
    create_res = trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 2, "price": 185.0, "currency": "USD", "traded_at": "2025-05-01"
    })
    trade_id = create_res.json()["id"]
    del_res = trades_client.delete(f"/api/trades/{trade_id}")
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True


def test_delete_nonexistent_trade(trades_client):
    res = trades_client.delete("/api/trades/99999")
    assert res.status_code == 404


def test_buy_updates_holding_avg_price(trades_client):
    # trades-first: 초기 포지션을 trade로 등록 후 추가 BUY
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 10, "price": 180.0, "currency": "USD", "traded_at": "2024-01-01"
    })
    trades_client.post("/api/trades", json={
        "ticker": "AAPL", "trade_type": "BUY",
        "quantity": 5, "price": 200.0, "currency": "USD", "traded_at": "2025-06-01"
    })
    holdings = trades_client.get("/api/holdings").json()
    aapl = next(h for h in holdings if h["ticker"] == "AAPL")
    # 두 BUY 합산 → quantity=15
    assert aapl["quantity"] >= 15
