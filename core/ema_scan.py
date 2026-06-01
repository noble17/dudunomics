"""EMA 골든크로스 유니버스 스캔 — 종가 기준, Telegram 발송."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import core.repository as repo
from core.data.prices_provider import fetch_ohlcv
from core.telegram import send_telegram

log = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

_TICKER_FILES = {
    "KR": [
        ("KOSPI200_PATH", "kospi200_tickers.json"),
        ("KOSDAQ150_PATH", "kosdaq150_tickers.json"),
    ],
    "US": [
        ("SP500_PATH", "sp500_tickers.json"),
        ("NASDAQ100_PATH", "nasdaq100_tickers.json"),
    ],
}

_MARKET_LABELS = {"KR": "국장", "US": "미장"}
_BATCH_SIZE = 50


def _load_tickers(market: str) -> list[str]:
    """유니버스 티커 리스트 반환 (중복 제거)."""
    seen: set[str] = set()
    result: list[str] = []
    for env_key, default_name in _TICKER_FILES[market]:
        path = Path(os.getenv(env_key, str(_DATA_DIR / default_name)))
        if not path.exists():
            log.warning("티커 파일 없음: %s", path)
            continue
        tickers = json.loads(path.read_text())
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


def _detect_golden_cross(close: pd.Series) -> dict | None:
    """
    EMA5 > EMA20 상태 확인.
    반환: {ema5, ema20, ema60, close, is_new_cross} or None (조건 미충족)
    최소 62 거래일 필요 (EMA60 워밍업).
    """
    if len(close) < 62:
        return None

    ema5 = close.ewm(span=5, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema60 = close.ewm(span=60, adjust=False).mean()

    curr_above = ema5.iloc[-1] > ema20.iloc[-1]
    if not curr_above:
        return None

    prev_above = ema5.iloc[-2] > ema20.iloc[-2]
    return {
        "ema5": round(ema5.iloc[-1], 2),
        "ema20": round(ema20.iloc[-1], 2),
        "ema60": round(ema60.iloc[-1], 2),
        "close": round(close.iloc[-1], 2),
        "is_new_cross": not prev_above,
    }


def _ticker_label(ticker: str, names: dict[str, str]) -> str:
    name = names.get(ticker)
    return f"{name} ({ticker})" if name else ticker


def _build_message(market: str, today: date,
                   new_entries: list[dict], maintained_entries: list[dict],
                   names: dict[str, str]) -> str:
    label = _MARKET_LABELS.get(market, market)
    lines = [f"📈 EMA 골든크로스 ({label} · {today})"]

    if new_entries:
        lines.append("\n🆕 신규")
        for e in new_entries:
            lines.append(
                f"• {_ticker_label(e['ticker'], names)} — 1일차\n"
                f"  현재가 {e['close']} | EMA5 {e['ema5']} | EMA20 {e['ema20']} | EMA60 {e['ema60']}"
            )

    if maintained_entries:
        lines.append("\n🔄 유지 중")
        for e in maintained_entries:
            lines.append(
                f"• {_ticker_label(e['ticker'], names)} — {e['day_count']}일차\n"
                f"  현재가 {e['close']} | EMA5 {e['ema5']} | EMA20 {e['ema20']} | EMA60 {e['ema60']}"
            )

    return "\n".join(lines)


def run_ema_scan(market: str) -> dict:
    """
    유니버스 EMA 골든크로스 스캔 실행.
    반환: {"new": int, "maintained": int}
    """
    tickers = _load_tickers(market)
    if not tickers:
        log.warning("ema_scan: 티커 없음 (market=%s)", market)
        return {"new": 0, "maintained": 0}

    today = date.today()
    end = today
    start = end - timedelta(days=130)  # 90 거래일 확보용 여유

    active_in_db: dict[str, dict] = {
        r["ticker"]: r for r in repo.get_active_golden_crosses(market)
    }

    new_entries: list[dict] = []
    maintained_entries: list[dict] = []
    names: dict[str, str] = repo.get_company_names(tickers)

    # 배치 단위로 OHLCV 조회
    for batch_start in range(0, len(tickers), _BATCH_SIZE):
        batch = tickers[batch_start:batch_start + _BATCH_SIZE]
        try:
            df, _ = fetch_ohlcv(batch, start, end)
        except Exception as e:
            log.error("ema_scan fetch_ohlcv 오류 (batch=%s): %s", batch[:3], e)
            continue

        if df.empty:
            continue

        available = df.columns.get_level_values(0).unique().tolist()

        for ticker in batch:
            if ticker not in available:
                continue
            try:
                close = df[ticker]["Close"].dropna()
                result = _detect_golden_cross(close)

                if result is None:
                    # 골든크로스 아님 → DB에 있으면 삭제
                    if ticker in active_in_db:
                        repo.delete_golden_cross(ticker)
                    continue

                if ticker not in active_in_db:
                    if result["is_new_cross"]:
                        repo.insert_golden_cross(ticker, market, names.get(ticker), today)
                        new_entries.append({**result, "ticker": ticker})
                else:
                    old = active_in_db[ticker]
                    new_count = old["day_count"] + 1
                    if new_count > 7:
                        repo.delete_golden_cross(ticker)
                    else:
                        repo.update_golden_cross(ticker, new_count)
                        maintained_entries.append({**result, "ticker": ticker, "day_count": new_count})

            except Exception as e:
                log.warning("ema_scan 티커 처리 오류 (%s): %s", ticker, e)

    if new_entries or maintained_entries:
        msg = _build_message(market, today, new_entries, maintained_entries, names)
        send_telegram(msg)

    log.info("ema_scan 완료: market=%s new=%d maintained=%d",
             market, len(new_entries), len(maintained_entries))
    return {"new": len(new_entries), "maintained": len(maintained_entries)}
