# M11: IndexStrip 완성 — DJI/VIX/US10Y/WTI/GOLD 실데이터 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** IndexStrip/MarketsPanel에서 "API 필요"로 표시되는 DJI·VIX·US10Y·WTI·GOLD 5개 지표를 FMP stable API + Stooq.com으로 실데이터 연결한다.

**Architecture:** `core/data/market_indices.py` 신규 파일에 FMP·Stooq HTTP 호출 + 5분 TTL 인메모리 캐시 순수 함수 구현 → `api/models.py` `QuotesOut` 5개 필드 추가 → `api/routers/quotes.py`에서 `market_indices` 호출 → 프론트엔드 타입 + `MarketsPanel` `quoteKey: null` → 실제 키로 교체.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, requests, Next.js 16, TypeScript, Tailwind CSS

**확인된 소스 (조사 완료):**
- DJI/VIX/GOLD: `https://financialmodelingprep.com/stable/quote?symbol={sym}&apikey={key}`
- US10Y: `https://financialmodelingprep.com/stable/treasury-rates?apikey={key}` → `year10` 필드
- WTI: `https://stooq.com/q/l/?s=cl.f&f=sd2t2ohlcv&h&e=csv` (인증 불필요)

---

## 파일 변경 목록

| 파일 | 변경 |
|------|------|
| `core/data/market_indices.py` | 신규 — FMP/Stooq 호출 + 5분 TTL 캐시 |
| `tests/test_market_indices.py` | 신규 — HTTP mock 단위 테스트 |
| `api/models.py` | `QuotesOut`에 DJI/VIX/US10Y/WTI/GOLD 필드 추가 |
| `api/routers/quotes.py` | `get_quotes` 엔드포인트에 5개 지표 연결 |
| `tests/test_quotes_api.py` | 신규 5개 필드 포함 테스트 추가 |
| `frontend/lib/types.ts` | `QuotesOut` 인터페이스에 5개 필드 추가 |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | `quoteKey: null` → 실제 키 5개 교체 |

---

### Task 1: market_indices.py 테스트 작성 (TDD Red)

**Files:**
- Create: `tests/test_market_indices.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_market_indices.py
"""core/data/market_indices 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import MagicMock, patch
import pytest


def _fmp_quote_resp(symbol: str, price: float, change_pct: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = [{"symbol": symbol, "price": price, "changePercentage": change_pct}]
    return m


def _fmp_empty_resp() -> MagicMock:
    m = MagicMock()
    m.json.return_value = []
    return m


def _treasury_resp(today: float, prev: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = [
        {"date": "2026-05-31", "year10": today},
        {"date": "2026-05-30", "year10": prev},
    ]
    return m


def _stooq_resp(open_: float, close: float) -> MagicMock:
    m = MagicMock()
    m.text = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        f"CL.F,2026-05-31,23:00:00,{open_},91.0,86.0,{close},\n"
    )
    return m


def _stooq_empty_resp() -> MagicMock:
    m = MagicMock()
    m.text = "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    return m


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전후 캐시 초기화 (모듈 레벨 딕셔너리 공유 방지)."""
    import core.data.market_indices as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


class TestFetchFmpQuote:
    def test_returns_price_and_change_pct(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_fmp_quote_resp("^DJI", 42000.0, 0.5)):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is not None
        assert result["price"] == 42000.0
        assert result["change_pct"] == 0.5

    def test_returns_none_on_empty_response(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_fmp_empty_resp()):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is None

    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.setenv("FMP_API_KEY", "")
        import core.data.market_indices as mod
        result = mod._fetch_fmp_quote("^DJI")
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.market_indices import _fetch_fmp_quote
            result = _fetch_fmp_quote("^DJI")
        assert result is None


class TestFetchFmpTreasury10y:
    def test_price_and_change_pct_computed(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_treasury_resp(4.50, 4.40)):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is not None
        assert result["price"] == pytest.approx(4.50)
        expected_pct = round((4.50 - 4.40) / 4.40 * 100, 4)
        assert result["change_pct"] == pytest.approx(expected_pct)

    def test_returns_none_on_empty_response(self):
        m = MagicMock(); m.json.return_value = []
        with patch("core.data.market_indices.requests.get", return_value=m):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("conn error")):
            from core.data.market_indices import _fetch_fmp_treasury_10y
            result = _fetch_fmp_treasury_10y()
        assert result is None


class TestFetchStooqWti:
    def test_returns_close_and_change_pct(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_stooq_resp(85.0, 87.36)):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is not None
        assert result["price"] == pytest.approx(87.36)
        expected_pct = round((87.36 - 85.0) / 85.0 * 100, 4)
        assert result["change_pct"] == pytest.approx(expected_pct)

    def test_returns_none_on_empty_csv(self):
        with patch("core.data.market_indices.requests.get",
                   return_value=_stooq_empty_resp()):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("core.data.market_indices.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.market_indices import _fetch_stooq_wti
            result = _fetch_stooq_wti()
        assert result is None


class TestGetMarketIndices:
    def test_returns_all_five_keys(self):
        with (
            patch("core.data.market_indices._fetch_fmp_quote",
                  side_effect=lambda sym: {"price": 1.0, "change_pct": 0.1}),
            patch("core.data.market_indices._fetch_fmp_treasury_10y",
                  return_value={"price": 4.5, "change_pct": 0.2}),
            patch("core.data.market_indices._fetch_stooq_wti",
                  return_value={"price": 87.0, "change_pct": -0.5}),
        ):
            from core.data.market_indices import get_market_indices
            result = get_market_indices()
        assert set(result.keys()) == {"DJI", "VIX", "GOLD", "US10Y", "WTI"}
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_market_indices.py -v 2>&1 | tail -15
```

예상: `ModuleNotFoundError: No module named 'core.data.market_indices'`

---

### Task 2: market_indices.py 구현 (TDD Green)

**Files:**
- Create: `core/data/market_indices.py`

- [ ] **Step 1: 파일 작성**

```python
# core/data/market_indices.py
"""시장 지표 — DJI/VIX/US10Y/WTI/GOLD 현재 시세.

소스:
- DJI, VIX, GOLD: FMP /stable/quote (FMP_API_KEY 필요)
- US10Y: FMP /stable/treasury-rates (FMP_API_KEY 필요)
- WTI: Stooq /q/l/ CSV (인증 불필요)
"""
from __future__ import annotations

import csv
import io
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_FMP_BASE = "https://financialmodelingprep.com/stable"
_STOOQ_URL = "https://stooq.com/q/l/"
_TTL = 300.0  # 5분

_cache: dict[str, tuple[dict, float]] = {}


def _fetch_fmp_quote(symbol: str) -> dict | None:
    """FMP /stable/quote — 단일 심볼. {"price": float, "change_pct": float} or None."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return None

    cache_key = f"fmp:{symbol}"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            f"{_FMP_BASE}/quote",
            params={"symbol": symbol, "apikey": api_key},
            timeout=8,
        )
        r.raise_for_status()
        items = r.json()
        if not items:
            return None
        item = items[0]
        result: dict = {
            "price": float(item["price"]),
            "change_pct": round(float(item.get("changePercentage") or 0.0), 4),
        }
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("FMP quote 실패 (%s): %s", symbol, e)
        return None


def _fetch_fmp_treasury_10y() -> dict | None:
    """FMP /stable/treasury-rates → year10 수익률. {"price": float, "change_pct": float} or None."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return None

    cache_key = "fmp:treasury10y"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            f"{_FMP_BASE}/treasury-rates",
            params={"apikey": api_key},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        today_val = float(rows[0]["year10"])
        change_pct = 0.0
        if len(rows) >= 2 and rows[1].get("year10"):
            prev_val = float(rows[1]["year10"])
            if prev_val:
                change_pct = round((today_val - prev_val) / prev_val * 100, 4)
        result: dict = {"price": today_val, "change_pct": change_pct}
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("FMP treasury-rates 실패: %s", e)
        return None


def _fetch_stooq_wti() -> dict | None:
    """Stooq CL.F → WTI 현재가. {"price": float, "change_pct": float} or None."""
    cache_key = "stooq:cl.f"
    now = time.time()
    if cache_key in _cache:
        data, exp = _cache[cache_key]
        if now < exp:
            return data

    try:
        r = requests.get(
            _STOOQ_URL,
            params={"s": "cl.f", "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            timeout=8,
        )
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        row = next(reader, None)
        if not row:
            return None
        close = float(row["Close"])
        open_ = float(row["Open"]) if row.get("Open") else close
        change_pct = round((close - open_) / open_ * 100, 4) if open_ else 0.0
        result: dict = {"price": close, "change_pct": change_pct}
        _cache[cache_key] = (result, now + _TTL)
        return result
    except Exception as e:
        log.warning("Stooq WTI 실패: %s", e)
        return None


def get_market_indices() -> dict[str, dict | None]:
    """DJI, VIX, US10Y, WTI, GOLD 현재 시세 반환.

    Returns:
        {
            "DJI":   {"price": float, "change_pct": float} | None,
            "VIX":   {"price": float, "change_pct": float} | None,
            "US10Y": {"price": float, "change_pct": float} | None,
            "WTI":   {"price": float, "change_pct": float} | None,
            "GOLD":  {"price": float, "change_pct": float} | None,
        }
    """
    return {
        "DJI":   _fetch_fmp_quote("^DJI"),
        "VIX":   _fetch_fmp_quote("^VIX"),
        "GOLD":  _fetch_fmp_quote("GCUSD"),
        "US10Y": _fetch_fmp_treasury_10y(),
        "WTI":   _fetch_stooq_wti(),
    }
```

- [ ] **Step 2: 테스트 실행 → PASS 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_market_indices.py -v 2>&1 | tail -20
```

예상: `12 passed`

- [ ] **Step 3: 커밋**

```bash
git add core/data/market_indices.py tests/test_market_indices.py
git commit -m "feat(m11): market_indices — FMP/Stooq DJI/VIX/US10Y/WTI/GOLD 조회 + 5분 캐시"
```

---

### Task 3: QuotesOut 모델 + quotes.py 연결

**Files:**
- Modify: `api/models.py` (QuotesOut 클래스)
- Modify: `api/routers/quotes.py`
- Modify: `tests/test_quotes_api.py`

- [ ] **Step 1: `api/models.py` QuotesOut에 5개 필드 추가**

`api/models.py`에서 현재 QuotesOut (line ~234):
```python
class QuotesOut(BaseModel):
    SPY: QuoteItem | None = None
    QQQ: QuoteItem | None = None
    USDKRW: QuoteItem | None = None
    BTC: QuoteItem | None = None
```

아래로 교체:
```python
class QuotesOut(BaseModel):
    SPY: QuoteItem | None = None
    QQQ: QuoteItem | None = None
    USDKRW: QuoteItem | None = None
    BTC: QuoteItem | None = None
    DJI: QuoteItem | None = None
    VIX: QuoteItem | None = None
    US10Y: QuoteItem | None = None
    WTI: QuoteItem | None = None
    GOLD: QuoteItem | None = None
```

- [ ] **Step 2: 엔드포인트 테스트에 5개 필드 mock 케이스 추가**

`tests/test_quotes_api.py` 파일 끝에 추가:

```python
def _mock_market_indices():
    return {
        "DJI":   {"price": 42000.0, "change_pct": 0.71},
        "VIX":   {"price": 15.32,   "change_pct": -2.67},
        "US10Y": {"price": 4.45,    "change_pct": 0.23},
        "WTI":   {"price": 87.36,   "change_pct": 1.40},
        "GOLD":  {"price": 4593.0,  "change_pct": 1.34},
    }


def test_quotes_includes_market_indices(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
        patch("api.routers.quotes.get_market_indices", side_effect=_mock_market_indices),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("DJI", "VIX", "US10Y", "WTI", "GOLD"):
        assert key in data
        assert data[key] is not None
        assert data[key]["price"] > 0


def test_quotes_market_indices_none_on_failure(quotes_client):
    """market_indices 실패 시 해당 필드 None, 나머지 정상."""
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
        patch("api.routers.quotes.get_market_indices",
              return_value={"DJI": None, "VIX": None, "US10Y": None, "WTI": None, "GOLD": None}),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("DJI", "VIX", "US10Y", "WTI", "GOLD"):
        assert data[key] is None
    # 기존 필드는 정상
    assert data["SPY"] is not None
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인 (엔드포인트 미수정)**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_quotes_api.py::test_quotes_includes_market_indices -v 2>&1 | tail -10
```

예상: `FAILED` (get_market_indices import 없음)

- [ ] **Step 4: `api/routers/quotes.py` 수정**

현재 파일 상단 import에 추가:
```python
from core.data.market_indices import get_market_indices
```

`get_quotes` 함수 맨 끝 `return result` 전에 추가:
```python
    # DJI / VIX / US10Y / WTI / GOLD
    try:
        indices = get_market_indices()
        for key, val in indices.items():
            if val is not None:
                setattr(result, key, _make_item(val["price"], val["change_pct"]))
    except Exception as e:
        log.warning("market_indices 조회 실패: %s", e)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_quotes_api.py -v 2>&1 | tail -15
```

예상: 모두 PASS

- [ ] **Step 6: 커밋**

```bash
git add api/models.py api/routers/quotes.py tests/test_quotes_api.py
git commit -m "feat(m11): QuotesOut에 DJI/VIX/US10Y/WTI/GOLD 추가 + quotes 엔드포인트 연결"
```

---

### Task 4: 프론트엔드 타입 + MarketsPanel 업데이트

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/terminal/panels/MarketsPanel.tsx`

- [ ] **Step 1: `frontend/lib/types.ts` QuotesOut 업데이트**

현재:
```typescript
export interface QuotesOut {
  SPY: QuoteItem | null
  QQQ: QuoteItem | null
  USDKRW: QuoteItem | null
  BTC: QuoteItem | null
}
```

교체:
```typescript
export interface QuotesOut {
  SPY: QuoteItem | null
  QQQ: QuoteItem | null
  USDKRW: QuoteItem | null
  BTC: QuoteItem | null
  DJI: QuoteItem | null
  VIX: QuoteItem | null
  US10Y: QuoteItem | null
  WTI: QuoteItem | null
  GOLD: QuoteItem | null
}
```

- [ ] **Step 2: `frontend/components/terminal/panels/MarketsPanel.tsx` quoteKey 업데이트**

현재 `INDEX_CONFIGS` 배열 (line ~21-28):
```typescript
  { label: "DJI",     quoteKey: null,   decimals: 0 },
  { label: "VIX",     quoteKey: null,   decimals: 2 },
  { label: "US10Y",   quoteKey: null,   decimals: 2 },
  { label: "WTI",     quoteKey: null,   decimals: 2 },
  { label: "GOLD",    quoteKey: null,   decimals: 0 },
```

아래로 교체:
```typescript
  { label: "DJI",     quoteKey: "DJI"   as keyof QuotesOut, decimals: 0 },
  { label: "VIX",     quoteKey: "VIX"   as keyof QuotesOut, decimals: 2 },
  { label: "US10Y",   quoteKey: "US10Y" as keyof QuotesOut, decimals: 2 },
  { label: "WTI",     quoteKey: "WTI"   as keyof QuotesOut, decimals: 2 },
  { label: "GOLD",    quoteKey: "GOLD"  as keyof QuotesOut, decimals: 0 },
```

- [ ] **Step 3: TypeScript 타입 체크**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit 2>&1 | head -20
```

예상: 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/lib/types.ts frontend/components/terminal/panels/MarketsPanel.tsx
git commit -m "feat(m11): 프론트엔드 QuotesOut 타입 + MarketsPanel quoteKey 실데이터 연결"
```

---

### Task 5: 최종 검증

- [ ] **Step 1: 전체 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/ 2>&1 | tail -5
```

예상: 전체 PASS (기존 172개 + 신규 ~14개)

- [ ] **Step 2: 프론트엔드 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx next build 2>&1 | tail -10
```

예상: 빌드 성공
