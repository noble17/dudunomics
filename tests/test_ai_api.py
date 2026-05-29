"""GET /api/ai/summary, POST /api/ai/chat 테스트"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def ai_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    import api.routers.ai as ai_mod
    ai_mod._summary_cache.clear()
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "ai@test.com", "password": "password123"})
    return c


def _mock_gemini_model(text: str):
    """generate_content() 반환값을 흉내내는 mock."""
    mock_response = MagicMock()
    mock_response.text = text
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    return mock_model


def test_ai_summary_returns_text(ai_client):
    """summary 엔드포인트: Gemini mock → 요약 텍스트 반환"""
    with patch("api.routers.ai.requests.get") as mock_news, \
         patch("api.routers.ai.genai.GenerativeModel") as mock_cls:
        # FMP 뉴스 mock
        mock_news.return_value.status_code = 200
        mock_news.return_value.json.return_value = [
            {"title": "SPY hits new high", "publishedDate": "2026-05-29", "url": "http://x.com", "site": "MW", "image": None}
        ]
        # Gemini mock
        mock_cls.return_value = _mock_gemini_model("SPY는 오늘 신고가를 기록했습니다.")
        res = ai_client.get("/api/ai/summary?ticker=SPY")
    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "SPY"
    assert len(body["summary"]) > 0


def test_ai_summary_requires_auth(fresh_db, monkeypatch):
    """인증 없이 → 401"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    res = c.get("/api/ai/summary?ticker=SPY")
    assert res.status_code == 401


def test_ai_chat_streams_response(ai_client):
    """chat 엔드포인트: SSE 스트리밍 응답 확인"""
    chunk1 = MagicMock()
    chunk1.text = "분석 "
    chunk2 = MagicMock()
    chunk2.text = "결과입니다."

    with patch("api.routers.ai.genai.GenerativeModel") as mock_cls:
        mock_model = MagicMock()
        mock_model.generate_content.return_value = iter([chunk1, chunk2])
        mock_cls.return_value = mock_model

        res = ai_client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "SPY 분석해줘"}], "ticker": "SPY"},
            headers={"Accept": "text/event-stream"},
        )
    assert res.status_code == 200
    body = res.text
    assert "data: " in body
