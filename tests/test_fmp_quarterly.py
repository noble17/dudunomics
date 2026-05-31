"""core/data/fmp_quarterly 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import patch, MagicMock


def _income_resp() -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = [
        {"symbol": "AAPL", "date": "2025-03-29", "period": "Q1", "calendarYear": "2025", "eps": 1.65, "revenue": 95359000000, "operatingIncome": 29631000000},
        {"symbol": "AAPL", "date": "2024-12-28", "period": "Q1", "calendarYear": "2024", "eps": 2.40, "revenue": 124300000000, "operatingIncome": 34054000000},
    ]
    return m


def _ratios_resp() -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = [
        {"symbol": "AAPL", "date": "2025-03-29", "period": "Q1", "calendarYear": "2025", "returnOnEquity": 1.234, "debtEquityRatio": 3.45},
        {"symbol": "AAPL", "date": "2024-12-28", "period": "Q1", "calendarYear": "2024", "returnOnEquity": 1.567, "debtEquityRatio": 4.12},
    ]
    return m


def test_fetch_fmp_quarterly_basic(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib; importlib.reload(fmp_quarterly)
    with patch("core.data.fmp_quarterly.requests.get") as mock_get:
        mock_get.side_effect = [_income_resp(), _ratios_resp()]
        rows = fmp_quarterly.fetch_fmp_quarterly("AAPL")
    assert len(rows) == 2
    row = next(r for r in rows if r["period"] == "2025Q1")
    assert row["ticker"] == "AAPL"
    assert row["eps"] == 1.65
    assert abs(row["revenue"] - 95359.0) < 1.0
    assert row["source"] == "fmp"


def test_roe_merged_from_ratios(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib; importlib.reload(fmp_quarterly)
    with patch("core.data.fmp_quarterly.requests.get") as mock_get:
        mock_get.side_effect = [_income_resp(), _ratios_resp()]
        rows = fmp_quarterly.fetch_fmp_quarterly("AAPL")
    row = next(r for r in rows if r["period"] == "2025Q1")
    assert abs(row["roe"] - 123.4) < 0.1
    assert abs(row["debt_ratio"] - 345.0) < 0.1


def test_korean_ticker_returns_empty(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib; importlib.reload(fmp_quarterly)
    assert fmp_quarterly.fetch_fmp_quarterly("005930.KS") == []


def test_missing_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    from core.data import fmp_quarterly
    import importlib; importlib.reload(fmp_quarterly)
    assert fmp_quarterly.fetch_fmp_quarterly("AAPL") == []
