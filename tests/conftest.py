import pytest
from pathlib import Path
import pandas as pd
import core.repository as repo_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.setenv("CHOICESTOCK_PREFETCH_DISABLED", "true")
    monkeypatch.setattr(repo_module, "DB_PATH", db_path)
    repo_module._engine = None
    yield
    if repo_module._engine is not None:
        repo_module._engine.dispose()
    repo_module._engine = None

@pytest.fixture
def client(fresh_db, monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "test@test.com", "password": "password123"})
    return c
