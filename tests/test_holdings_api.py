def test_list_holdings_empty(client):
    res = client.get("/api/holdings")
    assert res.status_code == 200
    assert res.json() == []

def test_upsert_and_list(client):
    res = client.put("/api/holdings/005930.KS", json={
        "name": "삼성전자", "currency": "KRW", "quantity": 10, "avg_price": 70000
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "005930.KS"
    assert data["quantity"] == 10
    res = client.get("/api/holdings")
    assert len(res.json()) == 1

def test_delete_holding(client):
    client.put("/api/holdings/AAPL", json={"name": "Apple", "currency": "USD", "quantity": 5, "avg_price": 175.0})
    res = client.delete("/api/holdings/AAPL")
    assert res.status_code == 200
    assert client.get("/api/holdings").json() == []

def test_cash_roundtrip(client):
    res = client.put("/api/holdings/cash", json={"cash_krw": 500000, "cash_usd": 200.0})
    assert res.status_code == 200
    res = client.get("/api/holdings/cash")
    data = res.json()
    assert data["cash_krw"] == 500000
    assert data["cash_usd"] == 200.0

def test_invalid_currency(client):
    res = client.put("/api/holdings/TSLA", json={"name": "Tesla", "currency": "EUR", "quantity": 1, "avg_price": 100})
    assert res.status_code == 422

def test_auth_required_when_env_set(monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USERNAME", "admin")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app, raise_server_exceptions=False)
    res = c.get("/api/holdings")  # no auth header
    assert res.status_code == 401
