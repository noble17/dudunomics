"""GET /api/news 테스트"""
import pytest
from unittest.mock import patch


FMP_RESPONSE = [
    {
        "title": "Amazon Hits Record High",
        "publishedDate": "2026-05-29 09:00:00",
        "url": "https://example.com/news/1",
        "site": "MarketWatch",
        "image": "https://example.com/img.png",
        "text": "full article text...",
        "symbol": "AMZN",
    }
]


@pytest.fixture
def news_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    import api.routers.news as news_mod
    news_mod._cache.clear()
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "news@test.com", "password": "password123"})
    return c


def test_news_returns_items(news_client):
    """정상 응답: FMP mock → NewsOut 구조"""
    with patch("api.routers.news.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = FMP_RESPONSE
        res = news_client.get("/api/news?ticker=AMZN&limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "AMZN"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["title"] == "Amazon Hits Record High"
    assert item["site"] == "MarketWatch"
    assert item["url"] == "https://example.com/news/1"


def test_news_no_fmp_key(fresh_db, monkeypatch):
    """FMP 키 미설정 → 503"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    import api.routers.news as news_mod
    news_mod._cache.clear()
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "nokey@test.com", "password": "password123"})
    res = c.get("/api/news?ticker=AMZN")
    assert res.status_code == 503


def test_news_requires_auth(fresh_db, monkeypatch):
    """인증 없이 → 401"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.setenv("FMP_API_KEY", "some-key")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/news?ticker=AMZN")
    assert res.status_code == 401
