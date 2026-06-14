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
         patch("api.routers.news.get_public_summary", return_value=None), \
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
         patch("api.routers.news.get_public_summary", return_value=None), \
         patch("yfinance.Ticker", return_value=mock_ticker):
        res = news_client.get("/api/news?ticker=AMZN")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_news_includes_choicestock_public_links(news_client):
    """초이스스탁 공개 summary 뉴스 링크를 기존 뉴스와 병합."""
    choice = {
        "news": [{
            "title": "루멘텀홀딩스, AI 성장 전략 제시",
            "published_date": "2026.06.10 03:06",
            "url": "https://www.choicestock.co.kr/stock/news_view/150978?bu=/search/summary/LITE",
            "site": "ChoiceStock public page",
        }]
    }
    mock_ticker = MagicMock()
    mock_ticker.news = []
    with patch("api.routers.news._fetch_news_native", return_value=[]), \
         patch("api.routers.news.repo.is_user_watchlist_ticker", return_value=True), \
         patch("api.routers.news.get_public_summary", return_value=choice), \
         patch("yfinance.Ticker", return_value=mock_ticker):
        res = news_client.get("/api/news?ticker=LITE&limit=10")
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["title"] == "루멘텀홀딩스, AI 성장 전략 제시"
    assert item["site"] == "ChoiceStock public page"


def test_news_skips_choicestock_when_not_in_watchlist(news_client):
    mock_ticker = MagicMock()
    mock_ticker.news = []
    with patch("api.routers.news._fetch_news_native", return_value=[]), \
         patch("api.routers.news.repo.is_user_watchlist_ticker", return_value=False), \
         patch("api.routers.news.get_public_summary") as choice, \
         patch("yfinance.Ticker", return_value=mock_ticker):
        res = news_client.get("/api/news?ticker=LITE&limit=10")
    assert res.status_code == 200
    assert res.json()["items"] == []
    choice.assert_not_called()


def test_news_requires_auth(fresh_db, monkeypatch):
    """인증 없이 → 401"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/news?ticker=AMZN")
    assert res.status_code == 401
