import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch


def _make_fake_ohlcv(ticker: str = "SPY", n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    close = 500 + np.cumsum(rng.normal(0, 1, n))
    ticker_df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(50_000_000, 100_000_000, n).astype(float),
    }, index=idx)
    return pd.concat({ticker: ticker_df}, axis=1)


@pytest.fixture
def candles_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "candles@test.com", "password": "password123"})
    return c


def test_candles_structure(candles_client):
    fake = _make_fake_ohlcv("SPY", 60)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=3M")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "SPY"
    assert data["period"] == "3M"
    assert len(data["candles"]) == 60
    c = data["candles"][0]
    for field in ("time", "open", "high", "low", "close", "volume"):
        assert field in c, f"candle missing field: {field}"
    assert c["high"] >= c["low"]


def test_candles_empty_ticker(candles_client):
    """데이터 없는 종목은 빈 candles 배열 반환 (4xx 아님)."""
    with patch("api.routers.candles.fetch_ohlcv", return_value=(pd.DataFrame(), [])):
        res = candles_client.get("/api/candles?ticker=UNKNOWN&period=1M")
    assert res.status_code == 200
    assert res.json()["candles"] == []


def test_candles_invalid_period(candles_client):
    """지원하지 않는 period는 422."""
    res = candles_client.get("/api/candles?ticker=SPY&period=INVALID")
    assert res.status_code == 422


def test_candles_requires_auth(fresh_db, monkeypatch):
    """인증 없이 접근 시 401."""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/candles?ticker=SPY")
    assert res.status_code == 401


def test_candles_with_indicators(candles_client):
    """indicators=true 요청 시 ma/bollinger/rsi/macd/volume_ma 포함."""
    fake = _make_fake_ohlcv("SPY", 200)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=1Y&indicators=true")
    assert res.status_code == 200
    data = res.json()
    assert data["indicators"] is not None
    ind = data["indicators"]
    assert set(ind.keys()) == {"ma", "bollinger", "rsi", "macd", "volume_ma"}
    assert set(ind["ma"].keys()) == {"5", "20", "60", "120"}
    assert len(ind["ma"]["5"]) > 0
    pt = ind["ma"]["5"][0]
    assert "time" in pt and "value" in pt


def test_candles_without_indicators_returns_null(candles_client):
    """indicators 파라미터 없으면 indicators 필드가 null."""
    fake = _make_fake_ohlcv("SPY", 60)
    with patch("api.routers.candles.fetch_ohlcv", return_value=(fake, [])):
        res = candles_client.get("/api/candles?ticker=SPY&period=3M")
    assert res.status_code == 200
    assert res.json()["indicators"] is None
