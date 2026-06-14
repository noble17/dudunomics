import pytest
from unittest.mock import patch, MagicMock


def test_send_telegram_missing_env(monkeypatch):
    """환경변수 없으면 False 반환, 예외 없음."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from core.telegram import send_telegram
    assert send_telegram("test") is False


def test_send_telegram_success(monkeypatch):
    """환경변수 있고 API 성공 → True 반환."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        from core.telegram import send_telegram
        result = send_telegram("hello")
    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "sendMessage" in call_args[0][0]
    assert call_args[1]["json"]["text"] == "hello"


def test_send_telegram_uses_channel_chat_id(monkeypatch):
    """채널별 chat id가 있으면 기본 chat id보다 우선."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("TELEGRAM_CHAT_ID_ALERTS", "111")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        from core.telegram import send_telegram
        result = send_telegram("alert", channel="alerts")
    assert result is True
    assert mock_post.call_args[1]["json"]["chat_id"] == "111"


def test_send_telegram_long_message(monkeypatch):
    """4096자 초과 메시지는 청크로 분할 전송."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    long_msg = "x" * 5000
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        from core.telegram import send_telegram
        send_telegram(long_msg)
    assert mock_post.call_count == 2  # 5000자 → 2 청크


def test_send_telegram_api_error(monkeypatch):
    """API 오류 시 False 반환, 예외 전파 안 함."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    with patch("httpx.post", side_effect=Exception("connection error")):
        from core.telegram import send_telegram
        assert send_telegram("test") is False
