import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ws_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "ws@test.com", "password": "password123"})
    return c


def test_get_workspace_empty(ws_client):
    res = ws_client.get("/api/workspace")
    assert res.status_code == 200
    assert res.json() == {"layout": {}, "name": "default"}


def test_save_and_get_workspace(ws_client):
    layout = {
        "panels": [20, 55, 25],
        "center_widgets": [{"i": "w1", "type": "portfolio", "x": 0, "y": 0, "w": 6, "h": 8}],
    }
    res = ws_client.put("/api/workspace", json={"layout": layout})
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    res2 = ws_client.get("/api/workspace")
    assert res2.status_code == 200
    assert res2.json()["layout"] == layout


def test_workspace_isolation(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c1 = TestClient(app)
    c1.post("/api/auth/signup", json={"email": "u1@test.com", "password": "password123"})
    c1.put("/api/workspace", json={"layout": {"widgets": ["portfolio"]}})

    c2 = TestClient(app)
    c2.post("/api/auth/signup", json={"email": "u2@test.com", "password": "password123"})
    res = c2.get("/api/workspace")
    assert res.json()["layout"] == {}
