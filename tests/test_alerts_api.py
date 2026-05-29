import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def alerts_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "alerts@test.com", "password": "password123"})
    return c


def test_list_alerts_empty(alerts_client):
    res = alerts_client.get("/api/alerts")
    assert res.status_code == 200
    assert res.json() == []


def test_create_and_list_alert(alerts_client):
    res = alerts_client.post("/api/alerts", json={
        "ticker": "AAPL",
        "condition_type": "price_above",
        "condition_value": 200.0,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["ticker"] == "AAPL"
    assert data["condition_type"] == "price_above"
    assert data["condition_value"] == 200.0
    assert "id" in data

    res2 = alerts_client.get("/api/alerts")
    assert len(res2.json()) == 1


def test_create_cross_alert_no_value(alerts_client):
    """골든크로스 조건은 condition_value 없어도 된다."""
    res = alerts_client.post("/api/alerts", json={
        "ticker": "SPY",
        "condition_type": "ma_golden_cross",
    })
    assert res.status_code == 201
    assert res.json()["condition_value"] is None


def test_delete_alert(alerts_client):
    create_res = alerts_client.post("/api/alerts", json={
        "ticker": "TSLA",
        "condition_type": "rsi_below",
        "condition_value": 30.0,
    })
    alert_id = create_res.json()["id"]

    del_res = alerts_client.delete(f"/api/alerts/{alert_id}")
    assert del_res.status_code == 204

    list_res = alerts_client.get("/api/alerts")
    assert list_res.json() == []


def test_delete_other_users_alert_fails(fresh_db, monkeypatch):
    """다른 유저의 알림은 삭제 불가."""
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "user1@test.com", "password": "password123"})
    c.post("/api/auth/signup", json={"email": "user2@test.com", "password": "password123"})

    # user1이 알림 생성
    login1 = c.post("/api/auth/login", json={"email": "user1@test.com", "password": "password123"})
    token1 = login1.cookies.get("access_token")
    create_res = c.post("/api/alerts",
        json={"ticker": "AAPL", "condition_type": "price_above", "condition_value": 200.0},
        cookies={"access_token": token1},
    )
    alert_id = create_res.json()["id"]

    # user2가 삭제 시도
    login2 = c.post("/api/auth/login", json={"email": "user2@test.com", "password": "password123"})
    token2 = login2.cookies.get("access_token")
    del_res = c.delete(f"/api/alerts/{alert_id}", cookies={"access_token": token2})
    assert del_res.status_code == 404


def test_alert_events_empty(alerts_client):
    res = alerts_client.get("/api/alerts/events")
    assert res.status_code == 200
    assert res.json() == []


def test_unread_events_and_read(fresh_db, monkeypatch):
    """insert_alert_event → unread 조회 → 읽음 처리 후 unread=0."""
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    import core.repository as repo
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "ev@test.com", "password": "password123"})

    # user_id=1로 이벤트 직접 삽입
    repo.insert_alert_event(
        user_id=1, alert_id=None, ticker="AAPL",
        condition_type="price_above", condition_value=200.0, triggered_price=201.5,
    )

    unread = c.get("/api/alerts/events/unread")
    assert unread.status_code == 200
    assert len(unread.json()) == 1

    read_res = c.post("/api/alerts/events/read")
    assert read_res.status_code == 204

    unread2 = c.get("/api/alerts/events/unread")
    assert unread2.json() == []
