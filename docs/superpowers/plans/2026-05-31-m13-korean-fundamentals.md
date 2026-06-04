# M13: 국내주식 PER/PBR 네이버 API 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.KS`/`.KQ` 종목의 `ExtendedSnapshot`에서 비어 있던 PER·PBR·EPS를 네이버 금융 `itemSummary` API로 채워, KOSPI200/KOSDAQ150 유니버스 퀀트 스코어링에 밸류에이션 데이터를 공급한다.

**Architecture:** `core/data/naver_fundamentals.py` 신규 파일에 네이버 `api.finance.naver.com/service/itemSummary.naver` 호출 + 10분 TTL 인메모리 캐시 구현 → `core/data/fundamentals_extended.py`의 `.KS`/`.KQ` 분기에서 네이버 데이터를 `ExtendedSnapshot`에 채움. 기존 미국 종목 흐름에는 변경 없음.

**Tech Stack:** Python 3.12, requests (이미 설치됨)

**확인된 API (조사 완료):**
- URL: `https://api.finance.naver.com/service/itemSummary.naver?itemcode={6자리코드}`
- Referer 헤더 필요: `https://finance.naver.com/`
- 응답 예시: `{"per": 25.62, "eps": 12372.0, "pbr": 4.41, "now": 317000, ...}`
- 티커 변환: `005930.KS` → itemcode `005930`

---

## 파일 변경 목록

| 파일 | 변경 |
|------|------|
| `core/data/naver_fundamentals.py` | 신규 — 네이버 itemSummary API + 10분 TTL 캐시 |
| `tests/test_naver_fundamentals.py` | 신규 — HTTP mock 단위 테스트 |
| `core/data/fundamentals_extended.py` | `_fetch_one` `.KS`/`.KQ` 분기에서 네이버 데이터 채우기 |

---

### Task 1: naver_fundamentals.py 테스트 작성 (TDD Red)

**Files:**
- Create: `tests/test_naver_fundamentals.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_naver_fundamentals.py
"""core/data/naver_fundamentals 단위 테스트 — 외부 HTTP 없음 (mock)."""
from datetime import date
from unittest.mock import MagicMock, patch
import pytest


def _naver_resp(per: float, pbr: float, eps: float) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "marketSum": 1853270318,
        "per": per,
        "eps": eps,
        "pbr": pbr,
        "now": 317000,
        "diff": 17500,
        "rate": 5.84,
        "quant": 32804208,
        "amount": 10306931,
        "high": 319000,
        "low": 305500,
        "risefall": 2,
    }
    return m


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전후 캐시 초기화."""
    import core.data.naver_fundamentals as mod
    mod._cache.clear()
    yield
    mod._cache.clear()


class TestTickerToCode:
    def test_ks_suffix(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("005930.KS") == "005930"

    def test_kq_suffix(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("035720.KQ") == "035720"

    def test_lowercase_ks(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("005930.ks") == "005930"

    def test_us_ticker_returns_none(self):
        from core.data.naver_fundamentals import _ticker_to_code
        assert _ticker_to_code("AAPL") is None
        assert _ticker_to_code("SPY") is None
        assert _ticker_to_code("005930") is None  # 접미사 없음


class TestFetchNaverSummary:
    def test_returns_per_pbr_eps(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(25.62, 4.41, 12372.0)):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("005930.KS")
        assert result is not None
        assert result["per"] == pytest.approx(25.62)
        assert result["pbr"] == pytest.approx(4.41)
        assert result["eps"] == pytest.approx(12372.0)

    def test_zero_values_become_none(self):
        m = MagicMock()
        m.json.return_value = {"per": 0, "pbr": 0, "eps": 0}
        with patch("core.data.naver_fundamentals.requests.get", return_value=m):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("000660.KS")
        assert result is not None
        assert result["per"] is None
        assert result["pbr"] is None
        assert result["eps"] is None

    def test_non_korean_returns_none(self):
        from core.data.naver_fundamentals import fetch_naver_summary
        assert fetch_naver_summary("AAPL") is None
        assert fetch_naver_summary("SPY") is None

    def test_returns_none_on_exception(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   side_effect=Exception("timeout")):
            from core.data.naver_fundamentals import fetch_naver_summary
            result = fetch_naver_summary("005930.KS")
        assert result is None

    def test_kq_ticker_uses_correct_code(self):
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(18.5, 2.1, 5000.0)) as mock_get:
            from core.data.naver_fundamentals import fetch_naver_summary
            fetch_naver_summary("035720.KQ")
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["itemcode"] == "035720"


class TestExtendedSnapshotIntegration:
    def test_ks_ticker_populated_from_naver(self):
        import core.data.naver_fundamentals as nav_mod
        nav_mod._cache.clear()
        with patch("core.data.naver_fundamentals.requests.get",
                   return_value=_naver_resp(25.62, 4.41, 12372.0)):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("005930.KS", date.today())
        assert snap.ticker == "005930.KS"
        assert snap.trailing_pe == pytest.approx(25.62)
        assert snap.pbr == pytest.approx(4.41)
        assert snap.eps_ttm == pytest.approx(12372.0)

    def test_ks_ticker_empty_on_naver_failure(self):
        import core.data.naver_fundamentals as nav_mod
        nav_mod._cache.clear()
        with patch("core.data.naver_fundamentals.requests.get",
                   side_effect=Exception("network error")):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("005930.KS", date.today())
        assert snap.ticker == "005930.KS"
        assert snap.trailing_pe is None
        assert snap.pbr is None

    def test_us_ticker_unaffected(self):
        """미국 종목은 기존 scraper 경로 유지 — naver 호출 없음."""
        with patch("core.data.fundamentals_extended._scrape", return_value=None):
            from core.data.fundamentals_extended import _fetch_one
            snap = _fetch_one("AAPL", date.today())
        assert snap.ticker == "AAPL"
        assert snap.error == "scrape_failed"
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_naver_fundamentals.py -v 2>&1 | tail -15
```

예상: `ModuleNotFoundError: No module named 'core.data.naver_fundamentals'`

---

### Task 2: naver_fundamentals.py 구현 (TDD Green)

**Files:**
- Create: `core/data/naver_fundamentals.py`

- [ ] **Step 1: 파일 작성**

```python
# core/data/naver_fundamentals.py
"""네이버 금융 itemSummary API — 국내 종목 PER/PBR/EPS.

엔드포인트: https://api.finance.naver.com/service/itemSummary.naver?itemcode={code}
인증 불필요. Referer 헤더 필수.
"""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

_TTL = 600.0  # 10분
_cache: dict[str, tuple[dict, float]] = {}
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def _ticker_to_code(ticker: str) -> str | None:
    """'005930.KS' → '005930', '035720.KQ' → '035720'. 국내 종목이 아니면 None."""
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return upper[:-3]
    return None


def fetch_naver_summary(ticker: str) -> dict | None:
    """네이버 itemSummary에서 per/pbr/eps 반환.

    Args:
        ticker: 종목 티커 (예: '005930.KS', '035720.KQ')

    Returns:
        {"per": float|None, "pbr": float|None, "eps": float|None} or None
        - 국내 종목이 아니면 None
        - 네트워크 오류 시 None
        - per/pbr/eps가 0이면 None으로 변환 (데이터 없음 의미)
    """
    code = _ticker_to_code(ticker)
    if not code:
        return None

    now = time.time()
    if code in _cache:
        data, exp = _cache[code]
        if now < exp:
            return data

    try:
        r = requests.get(
            "https://api.finance.naver.com/service/itemSummary.naver",
            params={"itemcode": code},
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        raw = r.json()

        def _safe(val: object) -> float | None:
            if val is None or val == 0:
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        result: dict = {
            "per": _safe(raw.get("per")),
            "pbr": _safe(raw.get("pbr")),
            "eps": _safe(raw.get("eps")),
        }
        _cache[code] = (result, now + _TTL)
        return result
    except Exception as e:
        log.debug("naver_fundamentals 실패 (%s): %s", ticker, e)
        return None
```

- [ ] **Step 2: 유닛 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_naver_fundamentals.py::TestTickerToCode tests/test_naver_fundamentals.py::TestFetchNaverSummary -v 2>&1 | tail -15
```

예상: `7 passed`

- [ ] **Step 3: 커밋**

```bash
git add core/data/naver_fundamentals.py tests/test_naver_fundamentals.py
git commit -m "feat(m13): naver_fundamentals — 네이버 itemSummary API PER/PBR/EPS + 10분 캐시"
```

---

### Task 3: fundamentals_extended.py — 국내 종목 분기 수정

**Files:**
- Modify: `core/data/fundamentals_extended.py` (`_fetch_one` 함수)

- [ ] **Step 1: `_fetch_one` 수정**

현재 `_fetch_one` 함수 (line ~55-85):
```python
def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    t_upper = ticker.upper()
    if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):
        return ExtendedSnapshot(ticker=ticker, as_of=as_of)
    ...
```

`if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):` 분기 본문을 교체:

```python
def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    t_upper = ticker.upper()
    if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):
        from core.data.naver_fundamentals import fetch_naver_summary
        nav = fetch_naver_summary(ticker)
        if nav:
            return ExtendedSnapshot(
                ticker=ticker,
                as_of=as_of,
                trailing_pe=nav["per"],
                pbr=nav["pbr"],
                eps_ttm=nav["eps"],
            )
        return ExtendedSnapshot(ticker=ticker, as_of=as_of)
    ...  # 이하 기존 코드 유지
```

- [ ] **Step 2: 통합 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_naver_fundamentals.py::TestExtendedSnapshotIntegration -v 2>&1 | tail -15
```

예상: `3 passed`

- [ ] **Step 3: 회귀 테스트 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_fundamentals_extended.py -v 2>&1 | tail -10
```

예상: 기존 테스트 전부 PASS (미국 종목 흐름 변경 없음)

- [ ] **Step 4: 커밋**

```bash
git add core/data/fundamentals_extended.py
git commit -m "feat(m13): .KS/.KQ 종목 ExtendedSnapshot에 네이버 PER/PBR/EPS 연결"
```

---

### Task 4: 최종 검증

- [ ] **Step 1: 전체 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/ 2>&1 | tail -5
```

예상: 전체 PASS (기존 172개 + 신규 ~12개)

- [ ] **Step 2: 실제 API 호출 연기 스모크 테스트 (선택)**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/python3 -c "
from core.data.naver_fundamentals import fetch_naver_summary
r = fetch_naver_summary('005930.KS')
print('삼성전자:', r)
r2 = fetch_naver_summary('035720.KQ')
print('카카오:', r2)
"
```

예상: `삼성전자: {'per': 25.62, 'pbr': 4.41, 'eps': 12372.0}` (값은 실시간 변동)
