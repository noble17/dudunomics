# tests/test_performance_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def perf_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "perf@test.com", "password": "password123"})
    return c


def test_performance_schema(perf_client):
    res = perf_client.get("/api/portfolio/performance?period=6m")
    assert res.status_code == 200
    data = res.json()
    assert "sharpe" in data
    assert "mdd" in data
    assert "total_return" in data
    assert "annualized_return" in data
    assert "benchmark" in data
    assert "chart" in data


def test_performance_no_snapshots_returns_zeros(perf_client):
    res = perf_client.get("/api/portfolio/performance")
    assert res.status_code == 200
    data = res.json()
    assert data["sharpe"] == 0.0
    assert data["mdd"] == 0.0


def test_sharpe_calculation():
    import core.repository as repo
    series = [
        {"date": "2025-01-01", "equity": 1000000},
        {"date": "2025-01-02", "equity": 1010000},
        {"date": "2025-01-03", "equity": 1005000},
        {"date": "2025-01-04", "equity": 1020000},
        {"date": "2025-01-05", "equity": 1015000},
    ]
    result = repo.calc_performance(series)
    assert isinstance(result["sharpe"], float)
    assert isinstance(result["mdd"], float)
    assert result["mdd"] <= 0   # MDD는 음수 또는 0


def test_mdd_calculation():
    import core.repository as repo
    series = [
        {"date": "2025-01-01", "equity": 1000000},
        {"date": "2025-01-02", "equity": 1100000},  # 고점
        {"date": "2025-01-03", "equity": 880000},   # -20% 낙폭
        {"date": "2025-01-04", "equity": 950000},
    ]
    result = repo.calc_performance(series)
    assert result["mdd"] <= -19.0  # 약 -20% MDD


def test_period_filter_invalid_defaults_to_6m(perf_client):
    res = perf_client.get("/api/portfolio/performance?period=invalid")
    assert res.status_code == 200


def test_yfinance_failure_graceful_fallback(perf_client):
    # fetch_index가 exception을 발생시켜도 200 반환 + benchmark는 비어야 함
    with patch("api.routers.portfolio.fetch_index", side_effect=RuntimeError("network error")):
        res = perf_client.get("/api/portfolio/performance?period=1m")
    assert res.status_code == 200
    data = res.json()
    assert data["benchmark"] == {}
    assert data["chart"] == []
