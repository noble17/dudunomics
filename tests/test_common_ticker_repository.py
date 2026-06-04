from datetime import date, datetime

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


def test_upsert_and_get_ticker_profile():
    import core.repository as repo

    repo.upsert_ticker_profile({
        "ticker": "BE",
        "name": "Bloom Energy Corporation",
        "market": "US",
        "country": "USA",
        "currency": "USD",
        "sector": "Technology",
        "industry": "Electrical Equipment",
        "exchange": "NYSE",
        "source": "test",
    })

    profile = repo.get_ticker_profile("BE")
    assert profile["ticker"] == "BE"
    assert profile["name"] == "Bloom Energy Corporation"
    assert profile["exchange"] == "NYSE"
    assert profile["updated_at"] is not None


def test_upsert_and_get_latest_fundamental_snapshot():
    import core.repository as repo

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
        "raw_json": {"hello": "world"},
    })

    snapshot = repo.get_latest_fundamental_snapshot("BE")
    assert snapshot["ticker"] == "BE"
    assert snapshot["source"] == "finviz"
    assert snapshot["peg"] == 0.6
    assert snapshot["raw_json"]["hello"] == "world"


def test_upsert_and_get_ticker_data_status():
    import core.repository as repo

    repo.upsert_ticker_data_status({
        "ticker": "BE",
        "data_type": "ohlcv",
        "source": "kis",
        "min_date": date(2025, 6, 1),
        "max_date": date(2026, 6, 3),
        "last_fetched_at": datetime(2026, 6, 3, 10, 0, 0),
        "last_success_at": datetime(2026, 6, 3, 10, 0, 0),
        "last_error": None,
        "coverage_json": {"rows": 252},
    })

    statuses = repo.get_ticker_data_status("BE")
    assert len(statuses) == 1
    assert statuses[0]["data_type"] == "ohlcv"
    assert statuses[0]["coverage_json"]["rows"] == 252
