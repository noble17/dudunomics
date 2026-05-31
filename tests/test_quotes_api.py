import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.prices.base import Price


@pytest.fixture
def quotes_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "q@test.com", "password": "password123"})
    return c


def _mock_kis_prices(tickers, **_):
    return {
        "SPY": Price(ticker="SPY", current=597.42, currency="USD", change_pct=1.23),
        "QQQ": Price(ticker="QQQ", current=519.87, currency="USD", change_pct=-0.45),
    }


def _mock_fx_rate(pair):
    return 1372.5


def _mock_btc():
    return Price(ticker="BTC", current=151234000.0, currency="KRW", change_pct=2.87)


def test_quotes_structure(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("SPY", "QQQ", "USDKRW", "BTC"):
        assert key in data
        assert data[key] is not None
        assert "price" in data[key]
        assert "change_abs" in data[key]
        assert "change_pct" in data[key]


def test_quotes_values(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
    ):
        res = quotes_client.get("/api/quotes")
    data = res.json()
    assert data["SPY"]["price"] == pytest.approx(597.42)
    assert data["QQQ"]["change_pct"] == pytest.approx(-0.45)
    assert data["USDKRW"]["price"] == pytest.approx(1372.5)
    assert data["USDKRW"]["change_pct"] == 0.0
    assert data["BTC"]["price"] == pytest.approx(151234000.0)


def test_quotes_partial_failure(quotes_client):
    """BTC 조회 실패해도 SPY/QQQ/USDKRW는 정상 반환."""
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=RuntimeError("Upbit 오류")),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    assert data["SPY"] is not None
    assert data["BTC"] is None


def test_quotes_requires_auth(fresh_db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    c = TestClient(app)
    res = c.get("/api/quotes")
    assert res.status_code == 401


def _mock_market_indices():
    return {
        "DJI":   {"price": 42000.0, "change_pct": 0.71},
        "VIX":   {"price": 15.32,   "change_pct": -2.67},
        "US10Y": {"price": 4.45,    "change_pct": 0.23},
        "WTI":   {"price": 87.36,   "change_pct": 1.40},
        "GOLD":  {"price": 4593.0,  "change_pct": 1.34},
    }


def test_quotes_includes_market_indices(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
        patch("api.routers.quotes.get_market_indices", side_effect=_mock_market_indices),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("DJI", "VIX", "US10Y", "WTI", "GOLD"):
        assert key in data
        assert data[key] is not None
        assert data[key]["price"] > 0


def test_quotes_market_indices_none_on_failure(quotes_client):
    """market_indices 실패 시 해당 필드 None, 나머지 정상."""
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
        patch("api.routers.quotes.get_market_indices",
              return_value={"DJI": None, "VIX": None, "US10Y": None, "WTI": None, "GOLD": None}),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("DJI", "VIX", "US10Y", "WTI", "GOLD"):
        assert data[key] is None
    # 기존 필드는 정상
    assert data["SPY"] is not None
