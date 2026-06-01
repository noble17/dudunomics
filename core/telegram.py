"""Telegram Bot API 전송 모듈."""
import logging
import os

import httpx

log = logging.getLogger(__name__)

_MAX_LEN = 4096


def send_telegram(text: str) -> bool:
    """Telegram 메시지 전송. 성공 True, 실패/미설정 False."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 전송 스킵")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [text[i:i + _MAX_LEN] for i in range(0, len(text), _MAX_LEN)]
    try:
        for chunk in chunks:
            httpx.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=10)
        return True
    except Exception as e:
        log.error("Telegram 전송 오류: %s", e)
        return False
