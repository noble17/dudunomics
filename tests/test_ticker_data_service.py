from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

import core.repository as repo_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(repo_module, "DB_PATH", db_path)
    repo_module._engine = None
    yield
    if repo_module._engine is not None:
        repo_module._engine.dispose()
    repo_module._engine = None


def _fake_prices(ticker="BE"):
    idx = pd.date_range("2026-01-02", periods=3, freq="B")
    frame = pd.DataFrame({
        "Open": [10.0, 11.0, 12.0],
        "High": [11.0, 12.0, 13.0],
        "Low": [9.0, 10.0, 11.0],
        "Close": [10.5, 11.5, 12.5],
        "Volume": [100, 120, 130],
    }, index=idx)
    return pd.concat({ticker: frame}, axis=1)


def test_get_price_history_is_cache_only():
    from core.data import ticker_data_service as svc

    with patch("core.data.ticker_data_service.fetch_ohlcv", return_value=(_fake_prices("BE"), [])) as fetch:
        out = svc.get_price_history("BE", date(2026, 1, 1), date(2026, 1, 10))

    fetch.assert_called_once_with(["BE"], date(2026, 1, 1), date(2026, 1, 10), cache_only=True)
    assert out["ticker"] == "BE"
    assert len(out["candles"]) == 3
    assert out["candles"][0]["time"] == "2026-01-02"


def test_get_fundamentals_prefers_snapshot_then_quant_score():
    import core.repository as repo
    from core.data import ticker_data_service as svc

    repo.upsert_fundamental_snapshot({
        "ticker": "BE",
        "as_of": date(2026, 6, 3),
        "source": "finviz",
        "per": None,
        "pbr": 12.3,
        "psr": 35.1,
        "peg": 0.6,
        "forward_pe": 69.47,
        "trailing_pe": None,
        "forward_eps": 104.03,
        "eps_ttm": None,
        "roe": None,
        "roic": None,
        "debt_ratio": None,
        "current_ratio": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_growth": 82.2,
        "eps_growth": None,
        "market_cap": None,
        "raw_json": {},
    })

    result = svc.get_fundamentals("BE", universe="sp500")
    assert result["ticker"] == "BE"
    assert result["valuation_source"] == "finviz"
    assert result["peg"] == 0.6
    assert result["forward_revenue_growth"] == 82.2


def test_hydrate_ohlcv_updates_status():
    from core.data import ticker_data_service as svc
    import core.repository as repo

    with patch("core.data.ticker_data_service.fetch_ohlcv", return_value=(_fake_prices("BE"), [])):
        result = svc.hydrate_ticker_data("BE", scopes=["ohlcv"])

    assert result["ticker"] == "BE"
    assert result["warnings"] == []
    statuses = repo.get_ticker_data_status("BE")
    assert statuses[0]["data_type"] == "ohlcv"
    assert statuses[0]["coverage_json"]["rows"] == 3


def test_hydrate_fundamental_updates_status(monkeypatch):
    from core.data import ticker_data_service as svc
    import core.repository as repo

    monkeypatch.setattr(
        "core.data.fundamental_backfill.hydrate_fundamental_snapshots",
        lambda tickers: {"requested": 1, "updated": 1, "skipped": 0, "errors": []},
    )

    result = svc.hydrate_ticker_data("BE", scopes=["fundamental"])

    assert result["ticker"] == "BE"
    assert result["warnings"] == []
    statuses = repo.get_ticker_data_status("BE")
    assert statuses[0]["data_type"] == "fundamental"
    assert statuses[0]["source"] == "finviz_stockanalysis"
    assert statuses[0]["coverage_json"] == {"requested": 1, "updated": 1, "skipped": 0}


def test_hydrate_fundamental_records_errors(monkeypatch):
    from core.data import ticker_data_service as svc
    import core.repository as repo

    monkeypatch.setattr(
        "core.data.fundamental_backfill.hydrate_fundamental_snapshots",
        lambda tickers: {"requested": 1, "updated": 0, "skipped": 1, "errors": ["ZZZ: fundamentals 없음"]},
    )

    result = svc.hydrate_ticker_data("ZZZ", scopes=["fundamental"])

    assert result["warnings"] == ["ZZZ: fundamentals 없음"]
    statuses = repo.get_ticker_data_status("ZZZ")
    assert statuses[0]["last_error"] == "ZZZ: fundamentals 없음"
