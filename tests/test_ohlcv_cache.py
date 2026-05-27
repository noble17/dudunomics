import pytest
from datetime import date
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


def test_get_ohlcv_range_empty():
    import core.repository as repo
    assert repo.get_ohlcv_range("AAPL") is None


def test_upsert_and_get_ohlcv_range():
    import core.repository as repo
    rows = [
        {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000},
        {"ticker": "AAPL", "date": date(2023, 1, 3), "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 1200000},
    ]
    repo.upsert_ohlcv_rows(rows)
    result = repo.get_ohlcv_range("AAPL")
    assert result == (date(2023, 1, 2), date(2023, 1, 3))


def test_upsert_ohlcv_rows_ignores_duplicate():
    import core.repository as repo
    row = {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000000}
    repo.upsert_ohlcv_rows([row])
    repo.upsert_ohlcv_rows([row])  # 중복 — 예외 없어야 함
    result = repo.get_ohlcv_range("AAPL")
    assert result == (date(2023, 1, 2), date(2023, 1, 2))


def test_get_ohlcv_range_multiple_tickers():
    import core.repository as repo
    repo.upsert_ohlcv_rows([
        {"ticker": "AAPL", "date": date(2023, 1, 2), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
    ])
    repo.upsert_ohlcv_rows([
        {"ticker": "MSFT", "date": date(2023, 2, 1), "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2},
    ])
    assert repo.get_ohlcv_range("AAPL") == (date(2023, 1, 2), date(2023, 1, 2))
    assert repo.get_ohlcv_range("MSFT") == (date(2023, 2, 1), date(2023, 2, 1))
    assert repo.get_ohlcv_range("TSLA") is None
