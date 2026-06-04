from unittest.mock import patch

import pytest


@pytest.fixture
def tickers_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "tickers@test.com", "password": "password123"})
    return c


def test_ticker_overview_returns_common_data(tickers_client):
    payload = {
        "ticker": "BE",
        "profile": {"ticker": "BE", "name": "Bloom Energy Corporation"},
        "fundamentals": {"ticker": "BE", "peg": 0.6, "valuation_source": "finviz"},
        "status": [],
    }
    with patch("api.routers.tickers.get_ticker_overview", return_value=payload):
        res = tickers_client.get("/api/tickers/BE/overview")
    assert res.status_code == 200
    assert res.json()["ticker"] == "BE"
    assert res.json()["fundamentals"]["peg"] == 0.6


def test_ticker_hydrate_delegates_scopes(tickers_client):
    payload = {"ticker": "BE", "scopes": ["ohlcv"], "warnings": [], "status": []}
    with patch("api.routers.tickers.hydrate_ticker_data", return_value=payload) as hydrate:
        res = tickers_client.post("/api/tickers/BE/hydrate?scopes=ohlcv")
    assert res.status_code == 200
    assert res.json()["ticker"] == "BE"
    hydrate.assert_called_once_with("BE", scopes=["ohlcv"])
