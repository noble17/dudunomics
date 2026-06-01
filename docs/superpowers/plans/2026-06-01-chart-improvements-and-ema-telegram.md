# 차트 가시성 개선 + EMA 골든크로스 Telegram 알람 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** EPS 예상 선·성장 차트 예상 막대 색상 개선 + 유니버스 전체 EMA 골든크로스 일별 Telegram 알람 (7일 반복)

**Architecture:** 프론트엔드 2개 컴포넌트 색상 수정 → `core/telegram.py` 전송 모듈 신규 → `core/ema_scan.py` 스캔 로직 신규 → `core/repository.py` DB 테이블 추가 → `core/scheduler.py` cron 잡 등록 → `api/routers/ema_scan.py` 수동 트리거 엔드포인트

**Tech Stack:** Next.js (Recharts), FastAPI, APScheduler, httpx, pandas ewm, DuckDB, Telegram Bot API

---

## 파일 구조

| 상태 | 파일 | 역할 |
|------|------|------|
| 수정 | `frontend/components/screener/price-chart.tsx` | eps_est 선 색상 amber로 변경 |
| 수정 | `frontend/components/screener/growth-chart.tsx` | 예상 막대 반투명 파랑으로 변경 |
| **신규** | `core/telegram.py` | `send_telegram(text)` — httpx로 Bot API 호출 |
| **신규** | `core/ema_scan.py` | `run_ema_scan(market)` — 스캔 + DB + Telegram |
| **신규** | `api/routers/ema_scan.py` | `POST /api/ema-scan/run` 수동 트리거 |
| **신규** | `tests/test_telegram.py` | telegram 모듈 단위 테스트 |
| **신규** | `tests/test_ema_scan.py` | ema_scan 로직 단위 테스트 |
| 수정 | `core/repository.py` | `golden_cross_events` 테이블 + CRUD |
| 수정 | `core/scheduler.py` | `ema_scan_kr_job` / `ema_scan_us_job` cron 추가 |
| 수정 | `api/main.py` | ema_scan 라우터 등록 |

---

## Task 1: price-chart.tsx — EPS 예상 선 색상 amber

**Files:**
- Modify: `frontend/components/screener/price-chart.tsx:248`

- [ ] **Step 1: eps_est 선 stroke 색상 변경**

`frontend/components/screener/price-chart.tsx` 248번 줄 수정:

```tsx
// 변경 전
<Line yAxisId="eps" type="stepAfter" dataKey="eps_est" stroke="#6b7280" dot={false} strokeWidth={2} strokeDasharray="5 4" name="eps_est" connectNulls />

// 변경 후
<Line yAxisId="eps" type="stepAfter" dataKey="eps_est" stroke="#fbbf24" dot={false} strokeWidth={2} strokeDasharray="5 4" name="eps_est" connectNulls />
```

- [ ] **Step 2: Legend formatter에 amber 표시 반영**

같은 파일 241번 줄 `Legend formatter` 수정:

```tsx
// 변경 전
formatter={(v: string) => v === "price" ? "● 주가" : v === "eps" ? "● 주당순이익" : "⋯ 예상 EPS"}

// 변경 후
formatter={(v: string) => v === "price" ? "● 주가" : v === "eps" ? "● 주당순이익" : "⋯ 예상 EPS (추정)"}
```

- [ ] **Step 3: 브라우저에서 확인**

```bash
# 개발 서버가 실행 중이라면 http://localhost:3333/screener/AAPL 접속
# 주가&EPS 탭 → 예상 EPS 점선이 amber(노란색)로 표시되는지 확인
gstack-browse http://localhost:3333/screener/AAPL
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/screener/price-chart.tsx
git commit -m "feat: EPS 예상 선 색상 amber로 개선"
```

---

## Task 2: growth-chart.tsx — 예상 막대 색상 반투명 파랑

**Files:**
- Modify: `frontend/components/screener/growth-chart.tsx:179`

- [ ] **Step 1: 예상 막대 Cell fill 색상 변경**

`frontend/components/screener/growth-chart.tsx` 179번 줄 수정:

```tsx
// 변경 전
fill={entry.is_estimate ? "var(--muted)" : "var(--color-chart-1, #3b82f6)"}

// 변경 후
fill={entry.is_estimate ? "rgba(59, 130, 246, 0.45)" : "var(--color-chart-1, #3b82f6)"}
```

- [ ] **Step 2: 브라우저에서 확인**

```bash
# http://localhost:3333/screener/AAPL 접속
# 성장성과 수익성 흐름은? 섹션 → 예상 연도 막대가 반투명 파란색으로 표시되는지 확인
gstack-browse http://localhost:3333/screener/AAPL
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/screener/growth-chart.tsx
git commit -m "feat: 성장 차트 예상 막대 반투명 파랑으로 개선"
```

---

## Task 3: core/telegram.py — Telegram 전송 모듈

**Files:**
- Create: `core/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_telegram.py` 생성:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics
.venv/bin/pytest tests/test_telegram.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.telegram'`

- [ ] **Step 3: core/telegram.py 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_telegram.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: 커밋**

```bash
git add core/telegram.py tests/test_telegram.py
git commit -m "feat: Telegram 전송 모듈 추가"
```

---

## Task 4: core/repository.py — golden_cross_events 테이블 + CRUD

**Files:**
- Modify: `core/repository.py`
- Create: `tests/test_golden_cross_repo.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_golden_cross_repo.py` 생성:

```python
from datetime import date
import pytest
import core.repository as repo


def test_insert_and_get_golden_cross(fresh_db):
    repo.insert_golden_cross("005930.KS", "KR", "삼성전자", date(2026, 6, 1))
    rows = repo.get_active_golden_crosses("KR")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "005930.KS"
    assert r["market"] == "KR"
    assert r["day_count"] == 1


def test_update_golden_cross_day_count(fresh_db):
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.update_golden_cross("AAPL", 2)
    rows = repo.get_active_golden_crosses("US")
    assert rows[0]["day_count"] == 2


def test_delete_golden_cross(fresh_db):
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.delete_golden_cross("AAPL")
    assert repo.get_active_golden_crosses("US") == []


def test_get_active_golden_crosses_filters_by_market(fresh_db):
    repo.insert_golden_cross("005930.KS", "KR", "삼성전자", date(2026, 6, 1))
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    kr = repo.get_active_golden_crosses("KR")
    us = repo.get_active_golden_crosses("US")
    assert len(kr) == 1 and kr[0]["ticker"] == "005930.KS"
    assert len(us) == 1 and us[0]["ticker"] == "AAPL"


def test_insert_golden_cross_idempotent(fresh_db):
    """동일 ticker 중복 INSERT → 기존 행 유지 (INSERT OR IGNORE)."""
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 1))
    repo.insert_golden_cross("AAPL", "US", "Apple", date(2026, 6, 2))  # 중복
    rows = repo.get_active_golden_crosses("US")
    assert len(rows) == 1
    assert str(rows[0]["first_detected_at"]) == "2026-06-01"  # 첫 감지일 유지
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_golden_cross_repo.py -v
```

Expected: `AttributeError: module 'core.repository' has no attribute 'insert_golden_cross'`

- [ ] **Step 3: _init_schema에 테이블 DDL 추가**

`core/repository.py`의 `_init_schema` 함수 내 `ddl` 문자열 끝(마지막 `"""` 직전)에 추가:

```python
    CREATE SEQUENCE IF NOT EXISTS golden_cross_events_id_seq START 1;
    CREATE TABLE IF NOT EXISTS golden_cross_events (
        id                 INTEGER DEFAULT nextval('golden_cross_events_id_seq') PRIMARY KEY,
        ticker             VARCHAR NOT NULL,
        market             VARCHAR NOT NULL,
        name               VARCHAR,
        first_detected_at  DATE NOT NULL,
        last_sent_at       TIMESTAMP,
        day_count          INTEGER DEFAULT 1,
        UNIQUE(ticker)
    );
```

- [ ] **Step 4: CRUD 함수 추가**

`core/repository.py` 파일 끝에 추가:

```python
def insert_golden_cross(ticker: str, market: str, name: str | None, first_date: date) -> None:
    """신규 골든크로스 등록. 이미 있으면 무시 (INSERT OR IGNORE)."""
    with session() as s:
        s.execute(text("""
            INSERT OR IGNORE INTO golden_cross_events
              (ticker, market, name, first_detected_at, last_sent_at, day_count)
            VALUES (:t, :m, :n, :fd, current_timestamp, 1)
        """), {"t": ticker, "m": market, "n": name, "fd": str(first_date)})
        s.commit()


def get_active_golden_crosses(market: str) -> list[dict]:
    """시장별 활성 골든크로스 전체 조회."""
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, market, name, first_detected_at, last_sent_at, day_count
            FROM golden_cross_events WHERE market = :m
        """), {"m": market}).fetchall()
        return [
            {"ticker": r[0], "market": r[1], "name": r[2],
             "first_detected_at": r[3], "last_sent_at": r[4], "day_count": r[5]}
            for r in rows
        ]


def update_golden_cross(ticker: str, day_count: int) -> None:
    """day_count 업데이트 + last_sent_at 갱신."""
    with session() as s:
        s.execute(text("""
            UPDATE golden_cross_events
            SET day_count = :dc, last_sent_at = current_timestamp
            WHERE ticker = :t
        """), {"dc": day_count, "t": ticker})
        s.commit()


def delete_golden_cross(ticker: str) -> None:
    """골든크로스 종료 — 행 삭제."""
    with session() as s:
        s.execute(text("DELETE FROM golden_cross_events WHERE ticker = :t"), {"t": ticker})
        s.commit()
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_golden_cross_repo.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 6: 커밋**

```bash
git add core/repository.py tests/test_golden_cross_repo.py
git commit -m "feat: golden_cross_events 테이블 + CRUD 추가"
```

---

## Task 5: core/ema_scan.py — EMA 스캔 로직

**Files:**
- Create: `core/ema_scan.py`
- Create: `tests/test_ema_scan.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_ema_scan.py` 생성:

```python
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
    # 70일 하락 후 급반등 → EMA5가 EMA20을 돌파
    down = [100.0 - i * 0.3 for i in range(70)]
    up = [down[-1] + i * 3.0 for i in range(20)]
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
        down = [100.0 - i * 0.3 for i in range(70)]
        up = [down[-1] + i * 3.0 for i in range(20)]
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_ema_scan.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.ema_scan'`

- [ ] **Step 3: core/ema_scan.py 구현**

```python
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


def _build_message(market: str, today: date,
                   new_entries: list[dict], maintained_entries: list[dict]) -> str:
    label = _MARKET_LABELS.get(market, market)
    lines = [f"📈 EMA 골든크로스 ({label} · {today})"]

    if new_entries:
        lines.append("\n🆕 신규")
        for e in new_entries:
            lines.append(
                f"• {e['ticker']} — 1일차\n"
                f"  현재가 {e['close']} | EMA5 {e['ema5']} | EMA20 {e['ema20']} | EMA60 {e['ema60']}"
            )

    if maintained_entries:
        lines.append("\n🔄 유지 중")
        for e in maintained_entries:
            lines.append(
                f"• {e['ticker']} — {e['day_count']}일차\n"
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
                        repo.insert_golden_cross(ticker, market, None, today)
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
        msg = _build_message(market, today, new_entries, maintained_entries)
        send_telegram(msg)

    log.info("ema_scan 완료: market=%s new=%d maintained=%d",
             market, len(new_entries), len(maintained_entries))
    return {"new": len(new_entries), "maintained": len(maintained_entries)}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_ema_scan.py -v
```

Expected: 전체 PASSED

- [ ] **Step 5: 커밋**

```bash
git add core/ema_scan.py tests/test_ema_scan.py
git commit -m "feat: EMA 골든크로스 유니버스 스캔 모듈 추가"
```

---

## Task 6: core/scheduler.py — EMA 스캔 cron 잡 등록

**Files:**
- Modify: `core/scheduler.py`

- [ ] **Step 1: import 및 잡 함수 추가**

`core/scheduler.py` 상단 import 블록에 추가:

```python
from core.ema_scan import run_ema_scan
```

`create_scheduler` 함수 위에 두 함수 추가:

```python
def ema_scan_kr_job():
    """국장 EMA 골든크로스 스캔 — 매일 16:00 KST."""
    try:
        result = run_ema_scan("KR")
        log.info("ema_scan_kr 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_kr_job 오류: %s", e)


def ema_scan_us_job():
    """미장 EMA 골든크로스 스캔 — 매일 07:00 KST."""
    try:
        result = run_ema_scan("US")
        log.info("ema_scan_us 완료: %s", result)
    except Exception as e:
        log.error("ema_scan_us_job 오류: %s", e)
```

- [ ] **Step 2: create_scheduler에 cron 잡 등록**

`core/scheduler.py` `create_scheduler` 함수 내 기존 `return scheduler` 직전에 추가:

```python
    scheduler.add_job(ema_scan_kr_job, "cron", hour=16, minute=0,
                      id="ema_scan_kr", timezone="Asia/Seoul")
    scheduler.add_job(ema_scan_us_job, "cron", hour=7, minute=0,
                      id="ema_scan_us", timezone="Asia/Seoul")
```

- [ ] **Step 3: 기존 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_alert_check.py -v
```

Expected: 전체 PASSED (기존 알람 로직 영향 없음)

- [ ] **Step 4: 커밋**

```bash
git add core/scheduler.py
git commit -m "feat: EMA 골든크로스 스캔 cron 잡 등록 (국장 16:00 / 미장 07:00 KST)"
```

---

## Task 7: api/routers/ema_scan.py + main.py — 수동 트리거 엔드포인트

**Files:**
- Create: `api/routers/ema_scan.py`
- Modify: `api/main.py`

- [ ] **Step 1: 라우터 작성**

`api/routers/ema_scan.py` 생성:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from core.auth.deps import current_user, CurrentUser
from core.ema_scan import run_ema_scan

router = APIRouter(prefix="/api/ema-scan", tags=["ema-scan"])


@router.post("/run")
async def trigger_ema_scan(
    background_tasks: BackgroundTasks,
    market: str = Query(..., description="KR 또는 US"),
    user: CurrentUser = Depends(current_user),
):
    """EMA 골든크로스 스캔 즉시 실행 (백그라운드). Telegram 발송 포함."""
    if market not in ("KR", "US"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="market은 KR 또는 US")
    background_tasks.add_task(run_ema_scan, market)
    return {"status": "started", "market": market}
```

- [ ] **Step 2: main.py에 라우터 등록**

`api/main.py`에 추가:

```python
# import 블록 하단에 추가
from api.routers.ema_scan import router as ema_scan_router

# app.include_router 블록 하단에 추가
app.include_router(ema_scan_router)
```

- [ ] **Step 3: API 엔드포인트 테스트**

```bash
# 서버 실행 중인 상태에서
curl -X POST "http://localhost:8000/api/ema-scan/run?market=KR" \
  -H "Authorization: Bearer <JWT_TOKEN>"
# Expected: {"status": "started", "market": "KR"}

curl -X POST "http://localhost:8000/api/ema-scan/run?market=INVALID" \
  -H "Authorization: Bearer <JWT_TOKEN>"
# Expected: 400 {"detail": "market은 KR 또는 US"}
```

- [ ] **Step 4: 전체 테스트 스위트 통과 확인**

```bash
.venv/bin/pytest -v
```

Expected: 전체 PASSED

- [ ] **Step 5: 커밋**

```bash
git add api/routers/ema_scan.py api/main.py
git commit -m "feat: EMA 스캔 수동 트리거 엔드포인트 추가 (POST /api/ema-scan/run)"
```

---

## 최종 검증

- [ ] 서버 재시작 후 스케줄러 로그에서 `ema_scan_kr` / `ema_scan_us` 잡 등록 확인
- [ ] `.env`에 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 설정 후 `POST /api/ema-scan/run?market=KR` 호출 → Telegram 메시지 수신 확인
- [ ] `price-chart.tsx` — 예상 EPS 점선 amber 색상 확인
- [ ] `growth-chart.tsx` — 예상 막대 반투명 파랑 확인
