import pytest
from pathlib import Path
import pandas as pd
import backtesting.lib as btlib
import core.repository as repo_module


def _sma_compat(arr, n):
    """backtesting 0.3.3에서 제거된 btlib.SMA 호환 구현."""
    return pd.Series(arr).rolling(n, min_periods=1).mean().values


@pytest.fixture(autouse=True)
def patch_btlib_sma(monkeypatch):
    monkeypatch.setattr(btlib, "SMA", _sma_compat, raising=False)

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.setattr(repo_module, "DB_PATH", db_path)
    repo_module._engine = None
    yield
    if repo_module._engine is not None:
        repo_module._engine.dispose()
    repo_module._engine = None

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)
