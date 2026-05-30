# M9: KIS 해외 OHLCV 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 미장(NASDAQ/NYSE/AMEX) 일봉 OHLCV 소스를 yfinance bulk → KIS API 우선으로 전환하고, KIS 실패 시 yfinance fallback 유지

**Architecture:** `core/prices/kis.py`에 `fetch_ohlcv_overseas()` 추가 → `core/data/ohlcv_cache.py`의 `_fetch_and_store()`에서 해외 ticker를 KIS 우선 조회 후 실패 시 기존 yfinance bulk로 fallback

**Tech Stack:** Python, requests, pandas, pytest, unittest.mock

---

## 파일 맵

| 파일 | 역할 |
|------|------|
| `core/prices/kis.py` | `fetch_ohlcv_overseas()` + `_fetch_ohlcv_overseas_single()` 추가 |
| `core/data/ohlcv_cache.py` | `_fetch_and_store()` 해외 종목 분기 수정 |
| `tests/test_kis_ohlcv.py` | 신규 테스트 6개 |

---

## Task 1: `fetch_ohlcv_overseas()` 테스트 4개 작성 + 구현

**Files:**
- Create: `tests/test_kis_ohlcv.py`
- Modify: `core/prices/kis.py`

- [ ] **Step 1: 테스트 파일 작성**

`tests/test_kis_ohlcv.py` 전체 내용:

```python
"""KIS 해외 일봉 OHLCV 테스트 — 외부 HTTP 호출 없음 (mock)."""
from datetime import date
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _row(xymd: str, clos: float = 150.0) -> dict:
    return {
        "xymd": xymd,
        "open": str(round(clos * 0.99, 2)),
        "high": str(round(clos * 1.01, 2)),
        "low":  str(round(clos * 0.98, 2)),
        "clos": str(clos),
        "tvol": "1000000",
    }


def _resp(rows: list[dict], keyb: str = "") -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": {"keyb": keyb},
        "output2": rows,
    }
    return m


# ── fetch_ohlcv_overseas 단위 테스트 ─────────────────────────────────────────

class TestFetchOhlcvOverseas:
    START = date(2025, 1, 2)
    END   = date(2025, 3, 31)

    def test_success_single_page(self):
        """정상 5행 응답 → DataFrame shape/columns 검증."""
        rows = [_row(f"202503{d:02d}") for d in [31, 28, 27, 26, 25]]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_resp(rows)):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END, market="NASDAQ")

        assert not df.empty
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 5
        assert df.index.is_monotonic_increasing

    def test_pagination_two_pages(self):
        """2페이지 응답(keyb 있음→없음) → 행 합산 검증."""
        page1_rows = [_row(f"202503{d:02d}") for d in range(28, 20, -1)]  # 8행
        page2_rows = [_row(f"202501{d:02d}") for d in range(31, 23, -1)]  # 8행

        responses = [
            _resp(page1_rows, keyb="NEXTPAGE"),
            _resp(page2_rows, keyb=""),
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", side_effect=responses):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", date(2025, 1, 1), self.END)

        assert len(df) == 16
        assert df.index.is_monotonic_increasing

    def test_empty_output2_returns_empty_df(self):
        """output2=[] → 빈 DataFrame 반환."""
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_resp([])):
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END)

        assert df.empty

    def test_no_token_returns_empty_df(self):
        """KIS_APPKEY 없음(토큰 None) → 빈 DataFrame, requests.get 미호출."""
        with patch("core.prices.kis._get_token", return_value=None), \
             patch("core.prices.kis.requests.get") as mock_get:
            from core.prices.kis import fetch_ohlcv_overseas
            df = fetch_ohlcv_overseas("AAPL", self.START, self.END)

        assert df.empty
        mock_get.assert_not_called()


# ── ohlcv_cache 통합 테스트 ───────────────────────────────────────────────────

class TestOhlcvCacheKisIntegration:
    START = date(2025, 1, 2)
    END   = date(2025, 3, 31)

    def _fake_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Open": [150.0], "High": [155.0], "Low": [148.0],
            "Close": [152.0], "Volume": [1_000_000],
        }, index=pd.to_datetime(["2025-03-31"]))

    def test_uses_kis_for_overseas(self, fresh_db):
        """해외 ticker → KIS fetch 호출, yfinance bulk 미호출."""
        with patch("core.prices.kis.fetch_ohlcv_overseas", return_value=self._fake_df()) as mock_kis, \
             patch("core.data.ohlcv_cache._fetch_yfinance_bulk") as mock_yf:
            from core.data.ohlcv_cache import _fetch_and_store
            _fetch_and_store(["AAPL"], self.START, self.END)

        mock_kis.assert_called_once_with("AAPL", self.START, self.END)
        mock_yf.assert_not_called()

    def test_fallback_to_yfinance_when_kis_empty(self, fresh_db):
        """KIS → 빈 DataFrame → yfinance bulk 호출 확인."""
        with patch("core.prices.kis.fetch_ohlcv_overseas", return_value=pd.DataFrame()), \
             patch("core.data.ohlcv_cache._fetch_yfinance_bulk", return_value={"AAPL": self._fake_df()}) as mock_yf, \
             patch("core.data.ohlcv_cache._store_df"):
            from core.data.ohlcv_cache import _fetch_and_store
            _fetch_and_store(["AAPL"], self.START, self.END)

        mock_yf.assert_called_once_with(["AAPL"], self.START, self.END)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
source .venv/bin/activate
python -m pytest tests/test_kis_ohlcv.py -v 2>&1 | tail -20
```

예상: `ImportError: cannot import name 'fetch_ohlcv_overseas' from 'core.prices.kis'`

- [ ] **Step 3: `fetch_ohlcv_overseas()` 구현**

`core/prices/kis.py` 파일 끝에 (기존 `fetch_ohlcv_domestic` 함수 아래) 두 함수를 추가한다.

```python
def _fetch_ohlcv_overseas_single(
    ticker: str,
    excd: str,
    start: date,
    end: date,
    token: str,
) -> pd.DataFrame:
    """단일 EXCD로 KIS 해외 일봉 조회. 페이지네이션 최대 5회."""
    all_rows: list[dict] = []
    keyb = ""

    for _ in range(5):
        try:
            res = requests.get(
                f"{KIS_BASE}/uapi/overseas-price/v1/quotations/dailyprice",
                params={
                    "AUTH": "",
                    "EXCD": excd,
                    "SYMB": ticker,
                    "GUBN": "0",
                    "BYMD": end.strftime("%Y%m%d"),
                    "MODP": "1",
                    "KEYB": keyb,
                },
                headers=_headers("HHDFS76240000", token),
                timeout=10,
            )
            data = res.json()
        except Exception as e:
            log.warning("KIS 해외 일봉 예외 (%s/%s): %s", ticker, excd, e)
            return pd.DataFrame()

        if data.get("rt_cd") != "0":
            log.debug("KIS 해외 일봉 오류 (%s/%s): %s", ticker, excd, data.get("msg1"))
            return pd.DataFrame()

        rows = data.get("output2") or []
        reached_start = False
        for row in rows:
            dt_str = row.get("xymd", "")
            if not dt_str:
                continue
            clos = float(row.get("clos") or 0)
            if clos <= 0:
                continue
            dt = datetime.strptime(dt_str, "%Y%m%d").date()
            if dt < start:
                reached_start = True
                continue
            all_rows.append({
                "date": dt,
                "Open": float(row.get("open") or 0),
                "High": float(row.get("high") or 0),
                "Low":  float(row.get("low") or 0),
                "Close": clos,
                "Volume": int(row.get("tvol") or 0),
            })

        if reached_start or not rows:
            break

        keyb = (data.get("output1") or {}).get("keyb", "")
        if not keyb:
            break

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates("date").sort_values("date")
    df.index = pd.to_datetime(df.pop("date"))
    return df


def fetch_ohlcv_overseas(
    ticker: str,
    start: date,
    end: date,
    market: str | None = None,
) -> pd.DataFrame:
    """KIS 해외주식 일봉 OHLCV. 미장(NAS/NYS/AMS) 대상, 최대 5페이지(500일).

    Returns DataFrame with DatetimeIndex, columns: Open High Low Close Volume
    빈 DataFrame이면 KIS 조회 실패 (caller에서 yfinance fallback).
    """
    token = _get_token()
    if not token:
        return pd.DataFrame()

    if market:
        first = _MARKET_TO_EXCD.get(market.upper())
        excd_list = [first] if first else ["NAS", "NYS", "AMS"]
    else:
        excd_list = ["NAS", "NYS", "AMS"]

    for excd in excd_list:
        df = _fetch_ohlcv_overseas_single(ticker, excd, start, end, token)
        if not df.empty:
            return df

    return pd.DataFrame()
```

- [ ] **Step 4: 테스트 4개 통과 확인**

```bash
python -m pytest tests/test_kis_ohlcv.py::TestFetchOhlcvOverseas -v
```

예상: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add core/prices/kis.py tests/test_kis_ohlcv.py
git commit -m "feat(m9): fetch_ohlcv_overseas — KIS 해외 일봉 조회 (NAS/NYS/AMS 페이지네이션)"
```

---

## Task 2: `_fetch_and_store()` 수정 + 테스트 2개 통과

**Files:**
- Modify: `core/data/ohlcv_cache.py:155-220`
- Modify: `tests/test_kis_ohlcv.py` (Task 1에서 이미 추가됨 — 이 단계에서 통과시킴)

- [ ] **Step 1: ohlcv_cache 테스트 실패 확인**

```bash
python -m pytest tests/test_kis_ohlcv.py::TestOhlcvCacheKisIntegration -v
```

예상: `2 failed` — `_fetch_and_store`가 아직 KIS를 호출하지 않아 `mock_kis.assert_called_once()` 실패

- [ ] **Step 2: `_fetch_and_store()` 수정**

`core/data/ohlcv_cache.py`에서 `_fetch_and_store()` 함수 전체를 교체한다.

현재 (`155~220`줄 범위):
```python
def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """OHLCV 다운로드 후 prices_cache에 저장.

    - 국내 종목: KIS API → FDR fallback (개별)
    - 해외 종목: yf.download() bulk 1회 호출 → 실패 종목만 개별 재시도
    """
    from core.prices.kis import fetch_ohlcv_domestic
```

교체 후 (`def _fetch_and_store` 전체):
```python
def _fetch_and_store(tickers: list[str], start: date, end: date) -> list[str]:
    """OHLCV 다운로드 후 prices_cache에 저장.

    - 국내 종목: KIS API → FDR fallback (개별)
    - 해외 종목: KIS API (개별) → 실패 종목만 yfinance bulk fallback
    """
    from core.prices.kis import fetch_ohlcv_domestic, fetch_ohlcv_overseas

    warns: list[str] = []
    domestic_tickers = [t for t in tickers if is_domestic(t)]
    overseas_tickers = [t for t in tickers if not is_domestic(t)]

    # ── 국내 종목: 개별 KIS/FDR ──────────────────────────────────────────────
    for ticker in domestic_tickers:
        df: pd.DataFrame = pd.DataFrame()
        try:
            df = fetch_ohlcv_domestic(ticker, start, end)
        except Exception as e:
            log.warning("KIS OHLCV 실패 (%s): %s — FDR fallback", ticker, e)

        if df.empty:
            try:
                df = _fetch_fdr(ticker, start, end)
            except Exception as e:
                warns.append(f"{ticker}: fetch 실패 — {e}")
                continue
            if df.empty:
                warns.append(f"{ticker}: 데이터 없음")
                continue

        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    # ── 해외 종목: KIS 우선 → yfinance fallback ──────────────────────────────
    if not overseas_tickers:
        return warns

    kis_failed: list[str] = []
    for ticker in overseas_tickers:
        df = fetch_ohlcv_overseas(ticker, start, end)
        if df.empty:
            kis_failed.append(ticker)
            continue
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    if not kis_failed:
        return warns

    # yfinance fallback — KIS 실패 종목만
    try:
        bulk = _fetch_yfinance_bulk(kis_failed, start, end)
    except YFRateLimitError:
        warns.append("해외 bulk: Yahoo Finance 요청 한도 초과. 잠시 후 다시 시도하세요.")
        return warns
    except Exception as e:
        log.warning("bulk download 실패: %s — 개별 재시도", e)
        bulk = {}

    failed = [t for t in kis_failed if t not in bulk]

    for ticker, df in bulk.items():
        try:
            _store_df(ticker, df)
        except Exception as e:
            warns.append(f"{ticker}: 저장 실패 — {e}")

    for ticker in failed:
        try:
            df = _fetch_yfinance(ticker, start, end)
            if df.empty:
                warns.append(f"{ticker}: 데이터 없음")
                continue
            _store_df(ticker, df)
        except YFRateLimitError:
            warns.append(f"{ticker}: Yahoo Finance 요청 한도 초과.")
        except Exception as e:
            warns.append(f"{ticker}: fetch 실패 — {e}")

    return warns
```

- [ ] **Step 3: 테스트 2개 통과 확인**

```bash
python -m pytest tests/test_kis_ohlcv.py::TestOhlcvCacheKisIntegration -v
```

예상: `2 passed`

- [ ] **Step 4: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/test_kis_ohlcv.py tests/test_candles_api.py tests/test_backtest_api.py -v 2>&1 | tail -20
```

예상: `test_kis_ohlcv 6 passed`, candles/backtest 기존 결과 변화 없음

- [ ] **Step 5: 커밋**

```bash
git add core/data/ohlcv_cache.py
git commit -m "feat(m9): _fetch_and_store — 해외 OHLCV KIS 우선, yfinance fallback"
```

---

## Task 3: 통합 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트 통과 확인**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

예상: 기존 6개 M9 신규 테스트 포함 127 passed, 20 failed (pre-existing 유지)

- [ ] **Step 2: 실제 API curl 검증**

서버가 실행 중이어야 한다. 새 터미널에서:

```bash
source .venv/bin/activate && uvicorn api.main:app --port 8000 &
sleep 3
```

JWT 토큰 획득:
```bash
TOKEN=$(curl -s -c /tmp/cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"noble8543@gmail.com","password":"zo0420zo!"}' \
  -b /tmp/cookies.txt | python3 -c "import sys,json; print('ok')" && \
  cat /tmp/cookies.txt | grep access_token | awk '{print $7}')
```

캔들 조회 (AAPL, 1M):
```bash
curl -s "http://localhost:8000/api/candles?ticker=AAPL&period=1M" \
  -H "Cookie: access_token=$TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('ticker:', d['ticker'])
print('candles:', len(d.get('candles', [])))
if d.get('candles'):
    print('first:', d['candles'][0])
    print('last:', d['candles'][-1])
"
```

예상: `ticker: AAPL`, `candles: 20~23` (영업일 기준 1개월), 정상 OHLCV 값

- [ ] **Step 3: KIS 로그 확인 (KIS 소스 확인)**

```bash
# 서버 로그에서 KIS 호출 여부 확인
# 서버 시작 시 로그에 "KIS 토큰 발급 성공" 또는 "파일 캐시 사용" 출력됨
# 캔들 조회 후 "KIS 해외 일봉" 관련 로그가 없으면 DB 캐시 HIT
# prices_cache를 비우고 재조회하면 KIS 호출 로그 확인 가능
```

```bash
# prices_cache AAPL 삭제 후 재조회
python3 -c "
import os; os.environ['DB_PATH']='data/dudunomics.duckdb'
from core import repository as repo
with repo.session() as s:
    from sqlalchemy import text
    s.execute(text(\"DELETE FROM prices_cache WHERE ticker='AAPL'\"))
    s.commit()
print('AAPL 캐시 삭제 완료')
"
```

이후 Step 2의 curl을 다시 실행하면 서버 로그에 KIS 호출 흔적 확인 가능.

- [ ] **Step 4: 최종 커밋 (필요 시)**

변경사항 없으면 스킵. 검증 중 수정이 생겼다면:

```bash
git add -p
git commit -m "fix(m9): KIS 해외 OHLCV 통합 검증 후 수정"
```
