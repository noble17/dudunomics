"""GET /api/news 테스트"""
import pytest
from unittest.mock import patch, MagicMock


YFINANCE_NEWS = [
    {
        "content": {
            "title": "Amazon Hits Record High",
            "pubDate": "2026-05-29T09:00:00Z",
            "canonicalUrl": {"url": "https://example.com/news/1"},
            "provider": {"displayName": "MarketWatch"},
            "thumbnail": {"originalUrl": "https://example.com/img.png", "resolutions": []},
        }
    }
]


@pytest.fixture
def news_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
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
    """정상 응답: yfinance mock → NewsOut 구조 (native provider는 빈 리스트로 mock)"""
    mock_ticker = MagicMock()
    mock_ticker.news = YFINANCE_NEWS
    # native provider를 비워서 yf fallback이 동작하도록 함
    with patch("api.routers.news._fetch_news_native", return_value=[]), \
         patch("yfinance.Ticker", return_value=mock_ticker):
        res = news_client.get("/api/news?ticker=AMZN&limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "AMZN"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["title"] == "Amazon Hits Record High"
    assert item["site"] == "MarketWatch"
    assert item["url"] == "https://example.com/news/1"


def test_news_returns_empty_when_no_news(news_client):
    """뉴스 없을 때 빈 리스트 반환 (native + yf 모두 빈 리스트)"""
    mock_ticker = MagicMock()
    mock_ticker.news = []
    with patch("api.routers.news._fetch_news_native", return_value=[]), \
         patch("yfinance.Ticker", return_value=mock_ticker):
        res = news_client.get("/api/news?ticker=AMZN")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_news_requires_auth(fresh_db, monkeypatch):
    """인증 없이 → 401"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/news?ticker=AMZN")
    assert res.status_code == 401
