import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

import core.repository as repo
from core.ema_scan import run_ema_scan, _detect_golden_cross


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _make_close(n: int, values: list[float] | None = None) -> pd.Series:
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    vals = values if values is not None else [100.0 + i * 0.1 for i in range(n)]
    return pd.Series(vals, index=idx, name="Close")


def _make_ohlcv_df(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "Open": close * 0.99, "High": close * 1.01,
        "Low": close * 0.98, "Close": close, "Volume": 1_000_000.0,
    })


def _make_multiindex_df(tickers_closes: dict[str, pd.Series]) -> pd.DataFrame:
    """{ticker: close_series} → MultiIndex DataFrame (ticker, field)."""
    frames = {}
    for ticker, close in tickers_closes.items():
        frames[ticker] = _make_ohlcv_df(close)
    return pd.concat(frames, axis=1)


# ── _detect_golden_cross 단위 테스트 ──────────────────────────────────

def test_detect_no_cross_insufficient_data():
    """데이터 부족(< 62행) → None 반환."""
    close = _make_close(30)
    assert _detect_golden_cross(close) is None


def test_detect_no_cross_when_ema5_below_ema20():
    """EMA5 < EMA20 상태 → None 반환."""
    # 하락 추세: EMA5가 EMA20 아래
    values = [100.0 - i * 0.5 for i in range(90)]
    close = _make_close(90, values)
    assert _detect_golden_cross(close) is None


def test_detect_new_cross():
    """EMA5가 EMA20을 상향 돌파 → is_new_cross=True."""
    # 89일 하락 후 마지막 1일 급반등 → EMA5가 EMA20을 방금 돌파
    down = [100.0 - i * 0.3 for i in range(89)]
    up = [down[-1] + 30.0]  # 마지막 1개만 급등해서 [-1]에서 크로스 발생
    close = _make_close(90, down + up)
    result = _detect_golden_cross(close)
    assert result is not None
    assert result["is_new_cross"] is True
    assert result["ema5"] > result["ema20"]
    assert "ema60" in result
    assert "close" in result


def test_detect_maintained_cross():
    """EMA5가 이미 EMA20 위에 있고 유지 중 → is_new_cross=False."""
    # 꾸준한 상승 추세: EMA5 > EMA20 유지
    values = [80.0 + i * 0.5 for i in range(90)]
    close = _make_close(90, values)
    result = _detect_golden_cross(close)
    assert result is not None
    assert result["is_new_cross"] is False


# ── run_ema_scan 통합 테스트 ───────────────────────────────────────────

def _mock_maintained_ohlcv(tickers, start, end):
    """꾸준한 상승 추세 OHLCV 반환 (EMA5 > EMA20 유지, is_new_cross=False)."""
    closes = {}
    for ticker in tickers:
        closes[ticker] = _make_close(90, [80.0 + i * 0.5 for i in range(90)])
    return _make_multiindex_df(closes), []


def _mock_new_cross_ohlcv(tickers, start, end):
    """EMA5가 EMA20을 방금 상향 돌파하는 OHLCV 반환 (is_new_cross=True)."""
    closes = {}
    for ticker in tickers:
        down = [100.0 - i * 0.3 for i in range(89)]
        up = [down[-1] + 30.0]  # 마지막 1개만 급등해서 [-1]에서 크로스 발생
        closes[ticker] = _make_close(90, down + up)
    return _make_multiindex_df(closes), []


def test_run_ema_scan_detects_new_cross(fresh_db, monkeypatch, tmp_path):
    """신규 골든크로스 감지 → DB insert + Telegram 전송."""
    ticker_file = tmp_path / "kospi200_tickers.json"
    ticker_file.write_text(json.dumps(["005930.KS"]))
    monkeypatch.setenv("KOSPI200_PATH", str(ticker_file))
    kosdaq_file = tmp_path / "kosdaq150_tickers.json"
    kosdaq_file.write_text(json.dumps([]))
    monkeypatch.setenv("KOSDAQ150_PATH", str(kosdaq_file))

    with patch("core.ema_scan.fetch_ohlcv", side_effect=_mock_new_cross_ohlcv), \
         patch("core.ema_scan.send_telegram", return_value=True) as mock_tg:
        result = run_ema_scan("KR")

    assert result["new"] == 1
    mock_tg.assert_called_once()
    msg = mock_tg.call_args[0][0]
    assert "골든크로스" in msg
    assert "국장" in msg
    assert "1일차" in msg


def test_run_ema_scan_maintained(fresh_db, monkeypatch, tmp_path):
    """이미 DB에 있는 티커 → day_count 증가."""
    ticker_file = tmp_path / "sp500_tickers.json"
    ticker_file.write_text(json.dumps(["AAPL"]))
    monkeypatch.setenv("SP500_PATH", str(ticker_file))
    nasdaq_file = tmp_path / "nasdaq100_tickers.json"
    nasdaq_file.write_text(json.dumps([]))
    monkeypatch.setenv("NASDAQ100_PATH", str(nasdaq_file))

    # 사전에 DB에 등록 (day_count=3)
    repo.insert_golden_cross("AAPL", "US", "Apple", date.today() - timedelta(days=3))
    repo.update_golden_cross("AAPL", 3)

    with patch("core.ema_scan.fetch_ohlcv", side_effect=_mock_maintained_ohlcv), \
         patch("core.ema_scan.send_telegram", return_value=True) as mock_tg:
        result = run_ema_scan("US")

    rows = repo.get_active_golden_crosses("US")
    assert rows[0]["day_count"] == 4
    assert result["maintained"] == 1
    mock_tg.assert_called_once()
    msg = mock_tg.call_args[0][0]
    assert "4일차" in msg


def test_run_ema_scan_expires_after_7_days(fresh_db, monkeypatch, tmp_path):
    """day_count=7인 티커 → 전송 후 DB에서 삭제."""
    ticker_file = tmp_path / "sp500_tickers.json"
    ticker_file.write_text(json.dumps(["AAPL"]))
    monkeypatch.setenv("SP500_PATH", str(ticker_file))
    nasdaq_file = tmp_path / "nasdaq100_tickers.json"
    nasdaq_file.write_text(json.dumps([]))
    monkeypatch.setenv("NASDAQ100_PATH", str(nasdaq_file))

    repo.insert_golden_cross("AAPL", "US", "Apple", date.today() - timedelta(days=7))
    repo.update_golden_cross("AAPL", 7)

    with patch("core.ema_scan.fetch_ohlcv", side_effect=_mock_maintained_ohlcv), \
         patch("core.ema_scan.send_telegram", return_value=True):
        run_ema_scan("US")

    assert repo.get_active_golden_crosses("US") == []


def test_run_ema_scan_no_telegram_when_nothing(fresh_db, monkeypatch, tmp_path):
    """골든크로스 없으면 Telegram 미발송."""
    ticker_file = tmp_path / "sp500_tickers.json"
    # 하락 추세 티커 — EMA5 < EMA20
    ticker_file.write_text(json.dumps(["AAPL"]))
    monkeypatch.setenv("SP500_PATH", str(ticker_file))
    nasdaq_file = tmp_path / "nasdaq100_tickers.json"
    nasdaq_file.write_text(json.dumps([]))
    monkeypatch.setenv("NASDAQ100_PATH", str(nasdaq_file))

    def _mock_no_cross(tickers, start, end):
        closes = {}
        for t in tickers:
            closes[t] = _make_close(90, [100.0 - i * 0.3 for i in range(90)])
        return _make_multiindex_df(closes), []

    with patch("core.ema_scan.fetch_ohlcv", side_effect=_mock_no_cross), \
         patch("core.ema_scan.send_telegram") as mock_tg:
        run_ema_scan("US")

    mock_tg.assert_not_called()
