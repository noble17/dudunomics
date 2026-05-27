import numpy as np
import pandas as pd
from unittest.mock import patch


def _make_fake_ohlcv(n=300):
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": rng.integers(1_000_000, 5_000_000, n),
    }, index=idx)
    return df


def test_list_strategies(client):
    res = client.get("/api/backtest/strategies")
    assert res.status_code == 200
    data = res.json()
    names = [s["name"] for s in data]
    assert "SMA Crossover" in names
    assert "Equal Weight" in names

    # 모든 전략에 description/icon/tags 필드가 있어야 함
    for s in data:
        assert "description" in s, f"{s['name']} missing description"
        assert "icon" in s, f"{s['name']} missing icon"
        assert "tags" in s, f"{s['name']} missing tags"
        assert isinstance(s["description"], str) and len(s["description"]) > 0
        assert isinstance(s["icon"], str) and len(s["icon"]) > 0
        assert isinstance(s["tags"], list) and len(s["tags"]) > 0


def test_run_backtest_synthetic(client):
    fake_df = _make_fake_ohlcv()
    with patch("yfinance.download", return_value=fake_df):
        res = client.post("/api/backtest/run", json={
            "ticker": "TEST",
            "strategy": "SMA Crossover",
            "params": {"fast": 5, "slow": 20},
            "period_start": "2021-01-01",
            "period_end": "2022-01-01",
        })
    assert res.status_code == 200
    data = res.json()
    assert "total_return" in data
    assert "equity_curve" in data
    assert len(data["equity_curve"]) > 0
    assert data["id"] >= 1


def test_run_backtest_empty_data(client):
    with patch("yfinance.download", return_value=pd.DataFrame()):
        res = client.post("/api/backtest/run", json={
            "ticker": "FAKE",
            "strategy": "SMA Crossover",
            "params": {"fast": 5, "slow": 20},
            "period_start": "2021-01-01",
            "period_end": "2022-01-01",
        })
    assert res.status_code == 422
