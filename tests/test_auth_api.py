"""auth 라우터 테스트: signup / login / me / 사용자 격리"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    return TestClient(app, raise_server_exceptions=True)


def test_me_unauthenticated(auth_client):
    res = auth_client.get("/api/auth/me")
    assert res.status_code == 401


def test_signup_success(auth_client):
    res = auth_client.post("/api/auth/signup", json={"email": "a@b.com", "password": "secret123"})
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "a@b.com"
    assert "id" in body
    assert "access_token" in auth_client.cookies


def test_signup_duplicate_email(auth_client):
    auth_client.post("/api/auth/signup", json={"email": "dup@b.com", "password": "secret123"})
    res = auth_client.post("/api/auth/signup", json={"email": "dup@b.com", "password": "another123"})
    assert res.status_code == 409


def test_signup_short_password(auth_client):
    res = auth_client.post("/api/auth/signup", json={"email": "c@b.com", "password": "123"})
    assert res.status_code == 422


def test_login_success(auth_client):
    auth_client.post("/api/auth/signup", json={"email": "user@b.com", "password": "mypassword"})
    auth_client.cookies.clear()

    res = auth_client.post("/api/auth/login", json={"email": "user@b.com", "password": "mypassword"})
    assert res.status_code == 200
    assert res.json()["email"] == "user@b.com"
    assert "access_token" in auth_client.cookies


def test_login_wrong_password(auth_client):
    auth_client.post("/api/auth/signup", json={"email": "u2@b.com", "password": "rightpass"})
    auth_client.cookies.clear()
    res = auth_client.post("/api/auth/login", json={"email": "u2@b.com", "password": "wrongpass"})
    assert res.status_code == 401


def test_me_after_login(auth_client):
    auth_client.post("/api/auth/signup", json={"email": "me@b.com", "password": "mypassword"})
    res = auth_client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "me@b.com"


def test_user_data_isolation(auth_client):
    """두 사용자의 holdings가 서로 격리됨을 검증."""
    # 사용자1 가입 + 종목 추가
    auth_client.post("/api/auth/signup", json={"email": "user1@b.com", "password": "password1"})
    auth_client.put("/api/holdings/AAPL", json={"name": "Apple", "currency": "USD", "quantity": 10, "avg_price": 150.0})
    user1_holdings = auth_client.get("/api/holdings").json()
    assert len(user1_holdings) == 1

    # 사용자2 가입 (쿠키 갱신됨)
    auth_client.post("/api/auth/signup", json={"email": "user2@b.com", "password": "password2"})
    user2_holdings = auth_client.get("/api/holdings").json()
    assert user2_holdings == []
