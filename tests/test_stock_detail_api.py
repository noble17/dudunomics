from unittest.mock import patch
from datetime import date


def test_financials_endpoint_returns_data(client):
    mock_financials = {
        "revenue": [{"year": "2024", "period_end": "2024", "value": 391035, "is_estimate": False}],
        "eps": [{"year": "2024", "period_end": "2024", "value": 6.09, "is_estimate": False}],
        "roe": [],
        "latest_report_date": "2026.05.26",
    }
    mock_snap = type("Snap", (), {
        "market_cap_m": 3_000_000.0,
        "trailing_pe": 30.0,
        "forward_pe": 28.0,
        "forward_eps": 7.5,
        "peg": 2.5,
        "price_to_sales": 8.0,
    })()
    with patch("api.routers.stock_detail.fetch_annual_financials", return_value=mock_financials), \
         patch("api.routers.stock_detail.fetch_fundamentals", return_value=mock_snap):
        resp = client.get("/api/screener/ticker/AAPL/financials?universe=sp500")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revenue"][0]["value"] == 391035
    assert body["latest_report_date"] == "2026.05.26"
    assert "metrics" in body
    assert body["metrics"]["market_cap_m"] == 3_000_000.0
    assert body["metrics"]["forward_eps"] == 7.5


def test_financials_endpoint_prefers_choicestock_metrics(client):
    mock_financials = {
        "revenue": [{"year": "2026", "period_end": "2026.06", "value": 2993.5, "is_estimate": True}],
        "eps": [],
        "roe": [],
        "latest_report_date": "2026.05.06",
        "choicestock": {
            "source": "ChoiceStock public page",
            "source_url": "https://www.choicestock.co.kr/search/summary/LITE",
            "as_of": "2026-06-14",
            "metrics": {
                "market_cap_m": 71697.0,
                "trailing_pe": 163.6,
                "forward_pe": 56.84,
                "peg": 0.74,
                "price_to_sales": 28.8,
                "as_of": "2026.06.12",
                "source": "ChoiceStock public page",
            },
        },
    }
    mock_snap = type("Snap", (), {
        "market_cap_m": 1.0,
        "trailing_pe": 2.0,
        "forward_pe": 3.0,
        "forward_eps": 4.0,
        "peg": 5.0,
        "price_to_sales": 6.0,
    })()
    with patch("api.routers.stock_detail.fetch_annual_financials", return_value=mock_financials), \
         patch("api.routers.stock_detail.fetch_fundamentals", return_value=mock_snap):
        resp = client.get("/api/screener/ticker/LITE/financials?universe=sp500")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["market_cap_m"] == 71697.0
    assert body["metrics"]["forward_pe"] == 56.84
    assert body["metrics"]["forward_eps"] == 4.0
    assert body["metrics"]["source"] == "ChoiceStock public page"
    assert body["metrics"]["as_of"] == "2026.06.12"


def test_financials_endpoint_enables_choicestock_only_for_watchlist(client):
    mock_financials = {
        "revenue": [],
        "eps": [],
        "roe": [],
        "latest_report_date": None,
        "choicestock": {},
    }
    with patch("api.routers.stock_detail.repo.is_user_watchlist_ticker", return_value=True), \
         patch("api.routers.stock_detail.fetch_annual_financials", return_value=mock_financials) as fetch, \
         patch("api.routers.stock_detail.fetch_fundamentals", return_value=None):
        resp = client.get("/api/screener/ticker/LITE/financials?universe=sp500")
    assert resp.status_code == 200
    fetch.assert_called_once_with("LITE", include_choicestock=True)


def test_financials_404_for_korean(client):
    with patch("api.routers.stock_detail.fetch_annual_financials", return_value=None):
        resp = client.get("/api/screener/ticker/005930.KS/financials")
    assert resp.status_code == 404


def test_price_chart_endpoint_returns_data(client):
    import pandas as pd
    import numpy as np
    from datetime import date, timedelta

    today = date.today()
    dates = pd.date_range(end=today, periods=10, freq="B")
    mock_df = pd.DataFrame(
        {("AAPL", "Close"): np.linspace(200, 210, 10)},
        index=dates,
    )
    with patch("api.routers.stock_detail.fetch_ohlcv", return_value=(mock_df, [])), \
         patch("api.routers.stock_detail.repo.get_quarterly_financials", return_value=[
             {"period": "2025Q1", "eps": 1.57}
         ]):
        resp = client.get("/api/screener/ticker/AAPL/price-chart")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["ohlcv"]) == 10
    assert "ema" in body
    assert "e5" in body["ema"]
    assert "e20" in body["ema"]
    assert "e60" in body["ema"]
    assert "e120" in body["ema"]
    assert len(body["quarterly_eps"]) == 1
    assert body["quarterly_eps"][0]["eps"] == 1.57
