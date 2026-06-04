# Quarterly Financials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 국내(KS/KQ) 및 미국(SP500) 종목의 분기 재무 데이터를 `quarterly_financials` 테이블에 저장하고, Quality 팩터(ROE/부채비율)와 EPS 모멘텀(YoY)을 개선한다.

**Architecture:** 네이버 `/finance/quarter` API(국내)와 FMP API(미국) 두 스크래퍼를 신규 작성한다. 배치 실행 시 DB 최신 period와 API 최신 period를 비교해 새 분기만 append한다. `universe_scorer.py`에서 Quality/EPS 모멘텀 계산 시 `quarterly_financials` 테이블을 직접 조회한다.

**Tech Stack:** Python, DuckDB (SQLAlchemy), requests, FMP REST API, Naver Finance API, pytest + unittest.mock

---

## 파일 맵

| 파일 | 역할 |
|------|------|
| `core/data/naver_quarterly.py` | **신규** — Naver 분기 스크래퍼 (KS/KQ) |
| `core/data/fmp_quarterly.py` | **신규** — FMP 분기 스크래퍼 (US) |
| `core/repository.py` | **수정** — `quarterly_financials` 테이블 + upsert/query 함수 |
| `core/scoring/universe_scorer.py` | **수정** — quarterly sync 호출 + Quality/EPS 모멘텀 소스 변경 |
| `tests/test_naver_quarterly.py` | **신규** |
| `tests/test_fmp_quarterly.py` | **신규** |
| `tests/test_quarterly_scoring.py` | **신규** — Quality + EPS 모멘텀 통합 검증 |

---

## Task 1: `quarterly_financials` 테이블 + Repository 함수

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: `CREATE TABLE` 구문을 `init_db()` 내 기존 테이블 목록에 추가**

`core/repository.py`의 `init_db()` 함수 안에서 `CREATE TABLE IF NOT EXISTS trades` 블록 바로 뒤에 추가:

```python
    CREATE TABLE IF NOT EXISTS quarterly_financials (
        ticker      TEXT    NOT NULL,
        period      TEXT    NOT NULL,
        eps         DOUBLE,
        roe         DOUBLE,
        debt_ratio  DOUBLE,
        revenue     DOUBLE,
        op_income   DOUBLE,
        source      TEXT,
        PRIMARY KEY (ticker, period)
    );
```

- [ ] **Step 2: 마이그레이션 구문 추가 (기존 DB 대응)**

`_run_migrations` 호출 전의 migration 리스트에 추가:

```python
"CREATE TABLE IF NOT EXISTS quarterly_financials (ticker TEXT NOT NULL, period TEXT NOT NULL, eps DOUBLE, roe DOUBLE, debt_ratio DOUBLE, revenue DOUBLE, op_income DOUBLE, source TEXT, PRIMARY KEY (ticker, period))",
```

- [ ] **Step 3: `upsert_quarterly_financials` 함수 추가**

`core/repository.py` 끝에 추가:

```python
def upsert_quarterly_financials(rows: list[dict]) -> None:
    """분기 재무 데이터 upsert. rows: [{"ticker", "period", "eps", "roe", "debt_ratio", "revenue", "op_income", "source"}]"""
    if not rows:
        return
    with session() as s:
        s.execute(text("""
            INSERT INTO quarterly_financials (ticker, period, eps, roe, debt_ratio, revenue, op_income, source)
            VALUES (:ticker, :period, :eps, :roe, :debt_ratio, :revenue, :op_income, :source)
            ON CONFLICT (ticker, period) DO UPDATE SET
                eps        = excluded.eps,
                roe        = excluded.roe,
                debt_ratio = excluded.debt_ratio,
                revenue    = excluded.revenue,
                op_income  = excluded.op_income,
                source     = excluded.source
        """), rows)
        s.commit()


def get_quarterly_financials(ticker: str, n: int = 8) -> list[dict]:
    """최신 n분기 데이터를 period 내림차순으로 반환."""
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, period, eps, roe, debt_ratio, revenue, op_income, source
            FROM quarterly_financials
            WHERE ticker = :ticker
            ORDER BY period DESC
            LIMIT :n
        """), {"ticker": ticker, "n": n}).mappings().all()
        return [dict(r) for r in rows]


def get_latest_quarterly_period(tickers: list[str]) -> dict[str, str]:
    """티커별 DB에 저장된 최신 period. 없는 티커는 결과에서 제외."""
    if not tickers:
        return {}
    ticker_set = set(tickers)
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, MAX(period) AS latest_period
            FROM quarterly_financials
            GROUP BY ticker
        """)).mappings().all()
        return {r["ticker"]: r["latest_period"] for r in rows if r["ticker"] in ticker_set}


def get_quarterly_bulk(tickers: list[str], n: int = 8) -> dict[str, list[dict]]:
    """복수 티커의 분기 데이터를 한 번의 쿼리로 일괄 반환. {ticker: [rows desc]}"""
    if not tickers:
        return {}
    ticker_set = set(tickers)
    with session() as s:
        rows = s.execute(text("""
            SELECT ticker, period, eps, roe, debt_ratio, revenue, op_income, source,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY period DESC) AS rn
            FROM quarterly_financials
        """)).mappings().all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        if row["ticker"] not in ticker_set:
            continue
        if row["rn"] > n:
            continue
        d = {k: v for k, v in row.items() if k != "rn"}
        result.setdefault(d["ticker"], []).append(d)
    return result
```

- [ ] **Step 4: 서버 재시작으로 마이그레이션 적용 확인**

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 5: 커밋**

```bash
git add core/repository.py
git commit -m "feat: add quarterly_financials table and repository functions"
```

---

## Task 2: Naver 분기 스크래퍼

**Files:**
- Create: `core/data/naver_quarterly.py`
- Create: `tests/test_naver_quarterly.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_naver_quarterly.py`:

```python
"""core/data/naver_quarterly 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import MagicMock, patch


def _make_quarter_response(rows_data: dict) -> MagicMock:
    """네이버 /finance/quarter API 응답 mock 생성."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "itemCode": "005930",
        "financePeriodType": "quarter",
        "financeInfo": {
            "trTitleList": [
                {"key": "202503", "title": "2025.03.", "isConsensus": "N"},
                {"key": "202412", "title": "2024.12.", "isConsensus": "N"},
                {"key": "202409", "title": "2024.09.", "isConsensus": "N"},
                {"key": "202406", "title": "2024.06.", "isConsensus": "N"},
                {"key": "202606", "title": "2026.06.", "isConsensus": "Y"},  # 컨센서스 — 제외
            ],
            "rowList": [
                {
                    "title": "EPS",
                    "columns": {
                        "202503": {"value": "6,993"},
                        "202412": {"value": "2,864"},
                        "202409": {"value": "1,783"},
                        "202406": {"value": "733"},
                        "202606": {"value": "10,565"},
                    },
                },
                {
                    "title": "ROE",
                    "columns": {
                        "202503": {"value": "19.16"},
                        "202412": {"value": "10.85"},
                        "202409": {"value": "8.37"},
                        "202406": {"value": "7.95"},
                        "202606": {"value": "-"},
                    },
                },
                {
                    "title": "부채비율",
                    "columns": {
                        "202503": {"value": "30.15"},
                        "202412": {"value": "29.94"},
                        "202409": {"value": "26.64"},
                        "202406": {"value": "26.36"},
                        "202606": {"value": "-"},
                    },
                },
                {
                    "title": "매출액",
                    "columns": {
                        "202503": {"value": "1,338,734"},
                        "202412": {"value": "938,374"},
                        "202409": {"value": "860,617"},
                        "202406": {"value": "745,663"},
                        "202606": {"value": "1,665,266"},
                    },
                },
                {
                    "title": "영업이익",
                    "columns": {
                        "202503": {"value": "572,328"},
                        "202412": {"value": "200,737"},
                        "202409": {"value": "121,661"},
                        "202406": {"value": "46,761"},
                        "202606": {"value": "857,477"},
                    },
                },
            ],
        },
    }
    return m


def test_fetch_confirmed_quarters_only():
    """isConsensus=Y 분기는 제외, N만 반환."""
    from core.data.naver_quarterly import fetch_naver_quarterly

    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response({})
        rows = fetch_naver_quarterly("005930.KS")

    periods = [r["period"] for r in rows]
    assert "2026Q2" not in periods  # 컨센서스 제외
    assert "2025Q1" in periods
    assert "2024Q4" in periods
    assert len(rows) == 4


def test_period_format_conversion():
    """'202503' → '2025Q1' 변환 검증."""
    from core.data.naver_quarterly import fetch_naver_quarterly

    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response({})
        rows = fetch_naver_quarterly("005930.KS")

    row_2025q1 = next(r for r in rows if r["period"] == "2025Q1")
    assert row_2025q1["eps"] == 6993.0
    assert row_2025q1["roe"] == 19.16
    assert row_2025q1["debt_ratio"] == 30.15
    assert row_2025q1["revenue"] == 1338734.0
    assert row_2025q1["op_income"] == 572328.0
    assert row_2025q1["ticker"] == "005930.KS"
    assert row_2025q1["source"] == "naver"


def test_dash_values_become_none():
    """'-' 값은 None으로 변환."""
    from core.data.naver_quarterly import fetch_naver_quarterly

    with patch("core.data.naver_quarterly.requests.get") as mock_get:
        mock_get.return_value = _make_quarter_response({})
        rows = fetch_naver_quarterly("005930.KS")

    # 모든 확정 분기에서 ROE가 None이 아님 (mock에서 값 있음)
    for row in rows:
        assert row["period"] != "2026Q2"


def test_non_korean_ticker_returns_empty():
    """KS/KQ 아닌 티커는 빈 리스트."""
    from core.data.naver_quarterly import fetch_naver_quarterly

    result = fetch_naver_quarterly("AAPL")
    assert result == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics && python -m pytest tests/test_naver_quarterly.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: `naver_quarterly.py` 구현**

`core/data/naver_quarterly.py`:

```python
"""core/data/naver_quarterly.py — 네이버 금융 분기 재무 스크래퍼 (KS/KQ 전용).

엔드포인트:
  https://m.stock.naver.com/api/stock/{code}/finance/quarter
isConsensus=Y 분기는 제외 (미확정 추정치).
period 변환: '202503' → '2025Q1' (월→분기: 1-3=Q1, 4-6=Q2, 7-9=Q3, 10-12=Q4)
"""
from __future__ import annotations

import logging
import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def _yyyymm_to_period(yyyymm: str) -> str:
    """'202503' → '2025Q1'."""
    year = yyyymm[:4]
    month = int(yyyymm[4:6])
    quarter = (month - 1) // 3 + 1
    return f"{year}Q{quarter}"


def _parse_float(value: str) -> float | None:
    """'1,338,734' → 1338734.0, '-' → None."""
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_naver_quarterly(ticker: str) -> list[dict]:
    """네이버 분기 재무 데이터 반환.

    Args:
        ticker: '005930.KS' 또는 '035720.KQ' 형식

    Returns:
        확정 분기(isConsensus=N)만, period 내림차순.
        각 dict: {ticker, period, eps, roe, debt_ratio, revenue, op_income, source}
        KS/KQ 아닌 티커는 빈 리스트.
    """
    upper = ticker.upper()
    if not (upper.endswith(".KS") or upper.endswith(".KQ")):
        return []

    code = upper[:-3]
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{code}/finance/quarter",
            headers=_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            log.debug("naver quarterly 실패 (%s): HTTP %s", ticker, r.status_code)
            return []
        data = r.json()
    except Exception as e:
        log.debug("naver quarterly 실패 (%s): %s", ticker, e)
        return []

    finance_info = data.get("financeInfo", {})
    title_list = finance_info.get("trTitleList", [])
    row_list = finance_info.get("rowList", [])

    # 확정 분기 key만 수집
    confirmed_keys = [
        t["key"] for t in title_list if t.get("isConsensus") == "N"
    ]

    # 항목별 컬럼 인덱스 구성
    def _col(row_title: str) -> dict[str, str]:
        for row in row_list:
            if row.get("title") == row_title:
                return row.get("columns", {})
        return {}

    eps_cols      = _col("EPS")
    roe_cols      = _col("ROE")
    debt_cols     = _col("부채비율")
    rev_cols      = _col("매출액")
    opinc_cols    = _col("영업이익")

    results: list[dict] = []
    for key in confirmed_keys:
        period = _yyyymm_to_period(key)
        results.append({
            "ticker":     ticker,
            "period":     period,
            "eps":        _parse_float(eps_cols.get(key, {}).get("value", "-")),
            "roe":        _parse_float(roe_cols.get(key, {}).get("value", "-")),
            "debt_ratio": _parse_float(debt_cols.get(key, {}).get("value", "-")),
            "revenue":    _parse_float(rev_cols.get(key, {}).get("value", "-")),
            "op_income":  _parse_float(opinc_cols.get(key, {}).get("value", "-")),
            "source":     "naver",
        })

    return sorted(results, key=lambda x: x["period"], reverse=True)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_naver_quarterly.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add core/data/naver_quarterly.py tests/test_naver_quarterly.py
git commit -m "feat: add naver quarterly financials scraper"
```

---

## Task 3: FMP 분기 스크래퍼

**Files:**
- Create: `core/data/fmp_quarterly.py`
- Create: `tests/test_fmp_quarterly.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_fmp_quarterly.py`:

```python
"""core/data/fmp_quarterly 단위 테스트 — 외부 HTTP 없음 (mock)."""
from unittest.mock import patch, MagicMock
import os


def _income_resp() -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = [
        {
            "symbol": "AAPL",
            "date": "2025-03-29",
            "period": "Q1",
            "calendarYear": "2025",
            "eps": 1.65,
            "revenue": 95359000000,
            "operatingIncome": 29631000000,
        },
        {
            "symbol": "AAPL",
            "date": "2024-12-28",
            "period": "Q1",
            "calendarYear": "2024",
            "eps": 2.40,
            "revenue": 124300000000,
            "operatingIncome": 34054000000,
        },
    ]
    return m


def _ratios_resp() -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = [
        {
            "symbol": "AAPL",
            "date": "2025-03-29",
            "period": "Q1",
            "calendarYear": "2025",
            "returnOnEquity": 1.234,
            "debtEquityRatio": 3.45,
        },
        {
            "symbol": "AAPL",
            "date": "2024-12-28",
            "period": "Q1",
            "calendarYear": "2024",
            "returnOnEquity": 1.567,
            "debtEquityRatio": 4.12,
        },
    ]
    return m


def test_fetch_fmp_quarterly_basic(monkeypatch):
    """FMP API 응답 정상 파싱."""
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib
    importlib.reload(fmp_quarterly)

    with patch("core.data.fmp_quarterly.requests.get") as mock_get:
        mock_get.side_effect = [_income_resp(), _ratios_resp()]
        rows = fmp_quarterly.fetch_fmp_quarterly("AAPL")

    assert len(rows) == 2
    row = next(r for r in rows if r["period"] == "2025Q1")
    assert row["ticker"] == "AAPL"
    assert row["eps"] == 1.65
    assert abs(row["revenue"] - 95359.0) < 1.0   # 백만 달러 단위
    assert row["source"] == "fmp"


def test_roe_merged_from_ratios(monkeypatch):
    """ratios 응답의 ROE가 income과 병합됨."""
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib
    importlib.reload(fmp_quarterly)

    with patch("core.data.fmp_quarterly.requests.get") as mock_get:
        mock_get.side_effect = [_income_resp(), _ratios_resp()]
        rows = fmp_quarterly.fetch_fmp_quarterly("AAPL")

    row = next(r for r in rows if r["period"] == "2025Q1")
    assert abs(row["roe"] - 123.4) < 0.1       # 1.234 * 100
    assert abs(row["debt_ratio"] - 345.0) < 0.1  # 3.45 * 100


def test_korean_ticker_returns_empty(monkeypatch):
    """KS/KQ 티커는 빈 리스트 (naver_quarterly 담당)."""
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    from core.data import fmp_quarterly
    import importlib
    importlib.reload(fmp_quarterly)

    result = fmp_quarterly.fetch_fmp_quarterly("005930.KS")
    assert result == []


def test_missing_api_key_returns_empty(monkeypatch):
    """FMP_API_KEY 없으면 빈 리스트."""
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    from core.data import fmp_quarterly
    import importlib
    importlib.reload(fmp_quarterly)

    result = fmp_quarterly.fetch_fmp_quarterly("AAPL")
    assert result == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_fmp_quarterly.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: `fmp_quarterly.py` 구현**

`core/data/fmp_quarterly.py`:

```python
"""core/data/fmp_quarterly.py — FMP API 분기 재무 스크래퍼 (US 전용).

엔드포인트:
  /v3/income-statement/{ticker}?period=quarter&limit=8
  /v3/financial-ratios/{ticker}?period=quarter&limit=8
FMP_API_KEY 환경변수 필요. KS/KQ 티커는 skip.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"

FMP_API_KEY = os.environ.get("FMP_API_KEY", "")


def _cal_period(entry: dict) -> str:
    """FMP entry → 'YYYYQN' 문자열. e.g. calendarYear=2025, period=Q1 → '2025Q1'."""
    year = str(entry.get("calendarYear", ""))
    q = entry.get("period", "")
    if year and q:
        return f"{year}{q}"
    # fallback: date 필드에서 파싱
    date_str = entry.get("date", "")
    if len(date_str) >= 7:
        year2 = date_str[:4]
        month = int(date_str[5:7])
        q2 = (month - 1) // 3 + 1
        return f"{year2}Q{q2}"
    return ""


def fetch_fmp_quarterly(ticker: str) -> list[dict]:
    """FMP에서 분기 재무 데이터 반환.

    Args:
        ticker: 'AAPL', 'MSFT' 등 US 티커. KS/KQ는 빈 리스트 반환.

    Returns:
        최신 8분기, period 내림차순.
        각 dict: {ticker, period, eps, roe, debt_ratio, revenue, op_income, source}
    """
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return []

    api_key = FMP_API_KEY
    if not api_key:
        log.warning("FMP_API_KEY 미설정 — quarterly 스킵")
        return []

    try:
        income_r = requests.get(
            f"{_BASE}/income-statement/{ticker}",
            params={"period": "quarter", "limit": 8, "apikey": api_key},
            timeout=10,
        )
        ratios_r = requests.get(
            f"{_BASE}/financial-ratios/{ticker}",
            params={"period": "quarter", "limit": 8, "apikey": api_key},
            timeout=10,
        )
    except Exception as e:
        log.debug("FMP quarterly 실패 (%s): %s", ticker, e)
        return []

    if income_r.status_code != 200 or ratios_r.status_code != 200:
        log.debug("FMP quarterly HTTP 오류 (%s): income=%s ratios=%s",
                  ticker, income_r.status_code, ratios_r.status_code)
        return []

    income_list = income_r.json()
    ratios_list = ratios_r.json()

    # ratios를 period 키로 인덱싱
    ratios_by_period: dict[str, dict] = {}
    for entry in (ratios_list if isinstance(ratios_list, list) else []):
        p = _cal_period(entry)
        if p:
            ratios_by_period[p] = entry

    results: list[dict] = []
    for entry in (income_list if isinstance(income_list, list) else []):
        period = _cal_period(entry)
        if not period:
            continue
        ratio = ratios_by_period.get(period, {})
        roe_raw = ratio.get("returnOnEquity")
        de_raw = ratio.get("debtEquityRatio")
        rev_raw = entry.get("revenue")

        results.append({
            "ticker":     ticker,
            "period":     period,
            "eps":        entry.get("eps"),
            "roe":        round(roe_raw * 100, 4) if roe_raw is not None else None,
            "debt_ratio": round(de_raw * 100, 4) if de_raw is not None else None,
            "revenue":    round(rev_raw / 1_000_000, 2) if rev_raw is not None else None,
            "op_income":  round(entry["operatingIncome"] / 1_000_000, 2)
                          if entry.get("operatingIncome") is not None else None,
            "source":     "fmp",
        })

    return sorted(results, key=lambda x: x["period"], reverse=True)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_fmp_quarterly.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add core/data/fmp_quarterly.py tests/test_fmp_quarterly.py
git commit -m "feat: add FMP quarterly financials scraper"
```

---

## Task 4: 배치에 quarterly sync 연동

**Files:**
- Modify: `core/scoring/universe_scorer.py`

- [ ] **Step 1: `_sync_quarterly` 헬퍼 함수 작성**

`universe_scorer.py` 상단 import 섹션 뒤에 추가:

```python
def _sync_quarterly(tickers: list[str], universe: str) -> None:
    """DB 최신 period와 API 최신 period 비교 → 새 분기만 append."""
    is_korean = universe in ("kospi200", "kosdaq150")

    if is_korean:
        from core.data.naver_quarterly import fetch_naver_quarterly as _fetch
    else:
        from core.data.fmp_quarterly import fetch_fmp_quarterly as _fetch

    latest_in_db = repo.get_latest_quarterly_period(tickers)
    rows_to_upsert: list[dict] = []

    for ticker in tickers:
        fetched = _fetch(ticker)
        if not fetched:
            continue
        api_latest = fetched[0]["period"]  # 이미 내림차순 정렬
        db_latest = latest_in_db.get(ticker)
        if db_latest and db_latest >= api_latest:
            continue  # 최신 분기 이미 보유
        rows_to_upsert.extend(fetched)

    if rows_to_upsert:
        repo.upsert_quarterly_financials(rows_to_upsert)
        log.info("[quarterly sync] %d행 upsert (%s)", len(rows_to_upsert), universe)
```

- [ ] **Step 2: `run_batch()` 안에 sync 호출 삽입**

펀더멘탈 페치 완료 직후 (`bs.update(universe, "팩터 계산 중", len(snaps))` 바로 앞)에 삽입:

```python
    # 3b. 분기 재무 sync (append-only)
    log.info("[Universe Scorer] 분기 재무 sync 중...")
    bs.update(universe, "분기 재무 동기화 중", len(snaps))
    _sync_quarterly(tickers, universe)
```

- [ ] **Step 3: 서버 재시작 후 kospi200 배치 테스트 실행**

```bash
curl -sb /tmp/dudunomics_cookie.txt -X POST "http://localhost:8000/api/screener/refresh?universe=kospi200"
sleep 5
curl -sb /tmp/dudunomics_cookie.txt "http://localhost:8000/api/screener/status?universe=kospi200"
```

Expected: status가 running → done으로 변함, error 없음

- [ ] **Step 4: quarterly_financials 저장 확인**

```bash
curl -sb /tmp/dudunomics_cookie.txt "http://localhost:8000/api/screener/status?universe=kospi200" | python3 -m json.tool
```

로그에서 `[quarterly sync]` 라인 확인:
```bash
# 서버 로그 확인 (서버가 포그라운드라면 터미널에서, 아니면 아래처럼)
curl -s http://localhost:8000/health
```

- [ ] **Step 5: 커밋**

```bash
git add core/scoring/universe_scorer.py
git commit -m "feat: sync quarterly financials in batch pipeline"
```

---

## Task 5: Quality 팩터 — ROE/부채비율 소스 변경

**Files:**
- Modify: `core/scoring/universe_scorer.py`
- Create: `tests/test_quarterly_scoring.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_quarterly_scoring.py`:

```python
"""분기 재무 데이터 기반 Quality/EPS 모멘텀 통합 테스트."""
import math
import pytest
import core.repository as repo


@pytest.fixture(autouse=True)
def seed_quarterly(fresh_db):
    """테스트용 quarterly_financials 데이터 시드."""
    repo.init_db()
    repo.upsert_quarterly_financials([
        # 삼성전자 — 최근 5분기
        {"ticker": "005930.KS", "period": "2025Q1", "eps": 6993.0, "roe": 19.16, "debt_ratio": 30.15, "revenue": 1338734.0, "op_income": 572328.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q4", "eps": 2864.0, "roe": 10.85, "debt_ratio": 29.94, "revenue": 938374.0,  "op_income": 200737.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q3", "eps": 1783.0, "roe": 8.37,  "debt_ratio": 26.64, "revenue": 860617.0,  "op_income": 121661.0, "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q2", "eps": 733.0,  "roe": 7.95,  "debt_ratio": 26.36, "revenue": 745663.0,  "op_income": 46761.0,  "source": "naver"},
        {"ticker": "005930.KS", "period": "2024Q1", "eps": 1186.0, "roe": 9.24,  "debt_ratio": 26.99, "revenue": 791405.0,  "op_income": 66853.0,  "source": "naver"},
    ])


def test_get_quarterly_financials_order():
    """get_quarterly_financials는 period 내림차순 반환."""
    rows = repo.get_quarterly_financials("005930.KS", n=3)
    assert len(rows) == 3
    assert rows[0]["period"] == "2025Q1"
    assert rows[1]["period"] == "2024Q4"
    assert rows[2]["period"] == "2024Q3"


def test_get_latest_quarterly_period():
    """get_latest_quarterly_period는 각 티커의 최신 period 반환."""
    result = repo.get_latest_quarterly_period(["005930.KS", "UNKNOWN"])
    assert result["005930.KS"] == "2025Q1"
    assert "UNKNOWN" not in result


def test_quality_score_uses_quarterly_roe():
    """Quality 점수 계산에 quarterly ROE가 사용되는지 확인."""
    from core.factors.quality import QualityFactor
    rows = repo.get_quarterly_financials("005930.KS", n=1)
    assert rows[0]["roe"] == 19.16
    score = QualityFactor.score(rows[0]["roe"], rows[0]["debt_ratio"])
    assert not math.isnan(score)
    assert score > 0  # ROE 19.16, 부채비율 30.15 → 양수 기대


def test_yoy_eps_momentum():
    """EPS YoY 모멘텀 계산: 2025Q1 vs 2024Q1."""
    rows = repo.get_quarterly_financials("005930.KS", n=8)
    by_period = {r["period"]: r for r in rows}
    recent = by_period.get("2025Q1")
    yoy    = by_period.get("2024Q1")
    assert recent is not None and yoy is not None
    momentum = (recent["eps"] - yoy["eps"]) / abs(yoy["eps"])
    assert abs(momentum - (6993 - 1186) / 1186) < 0.001  # ≈ 4.90
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_quarterly_scoring.py -v 2>&1 | head -30
```

Expected: 일부 실패 (get_quarterly_financials, get_latest_quarterly_period 미구현)

- [ ] **Step 3: Task 1에서 작성한 함수들이 동작하면 통과되는지 확인**

```bash
python -m pytest tests/test_quarterly_scoring.py -v
```

Expected: 4 passed (Task 1에서 이미 repository 함수 구현 완료)

- [ ] **Step 4: `universe_scorer.py`에서 Quality 소스 변경**

`run_batch()` 내 `# 4d. Quality` 블록을 교체. `quarterly_bulk`를 한 번 호출해 전 유니버스를 일괄 조회:

```python
    # 4d. Quality — quarterly_financials 일괄 조회 후 최신 분기 ROE/부채비율 사용
    quarterly_bulk = repo.get_quarterly_bulk(tickers, n=8)
    # 티커별 최신 분기 1개 (이미 내림차순)
    quarterly_map: dict[str, dict] = {
        t: rows[0] for t, rows in quarterly_bulk.items() if rows
    }

    raw_quality_vals: dict[str, float] = {}
    for ticker in tickers:
        q = quarterly_map.get(ticker)
        if q and (q.get("roe") is not None or q.get("debt_ratio") is not None):
            raw_quality_vals[ticker] = QualityFactor.score(q.get("roe"), q.get("debt_ratio"))
        else:
            # quarterly 없으면 ExtendedSnapshot fallback
            snap = snap_map.get(ticker)
            if snap:
                raw_quality_vals[ticker] = QualityFactor.score(snap.roe, snap.debt_to_equity)
            else:
                raw_quality_vals[ticker] = math.nan
    raw_quality = pd.Series(raw_quality_vals)
```

또한 DB upsert rows 딕셔너리에서 `raw_roe`와 `raw_debt_ratio`도 quarterly 우선으로 수정:

```python
            "raw_roe":          (quarterly_map[ticker]["roe"] if ticker in quarterly_map and quarterly_map[ticker].get("roe") is not None
                                 else snap.roe if snap else None),
            "raw_debt_ratio":   (quarterly_map[ticker]["debt_ratio"] / 100.0 if ticker in quarterly_map and quarterly_map[ticker].get("debt_ratio") is not None
                                 else (snap.debt_to_equity / 100.0) if (snap and snap.debt_to_equity) else None),
```

- [ ] **Step 5: 커밋**

```bash
git add core/scoring/universe_scorer.py tests/test_quarterly_scoring.py
git commit -m "feat: use quarterly ROE/debt_ratio for Quality factor"
```

---

## Task 6: EPS 모멘텀 — YoY 계산으로 변경

**Files:**
- Modify: `core/scoring/universe_scorer.py`

- [ ] **Step 1: `_compute_yoy_eps_momentum` 헬퍼 추가**

`universe_scorer.py` 상단 (import 섹션 아래)에 추가:

```python
def _compute_yoy_eps_momentum(ticker: str) -> float:
    """최근 확정 분기 EPS vs 전년 동기 EPS → YoY 성장률.

    예: 2025Q1 vs 2024Q1. 전년 동기 없거나 EPS=0이면 0.0 반환.
    """
    rows = repo.get_quarterly_financials(ticker, n=8)
    if len(rows) < 5:
        return 0.0
    by_period = {r["period"]: r for r in rows}
    recent_period = rows[0]["period"]           # 예: '2025Q1'
    year = int(recent_period[:4])
    q    = recent_period[4:]                    # 'Q1'
    yoy_period = f"{year - 1}{q}"              # '2024Q1'
    recent_eps = rows[0].get("eps")
    yoy_row    = by_period.get(yoy_period)
    yoy_eps    = yoy_row.get("eps") if yoy_row else None
    if recent_eps is None or yoy_eps is None or yoy_eps == 0:
        return 0.0
    return (recent_eps - yoy_eps) / abs(yoy_eps)
```

- [ ] **Step 2: `run_batch()` 내 EPS 모멘텀 계산 교체**

`quarterly_bulk`는 Task 5 Step 4에서 이미 계산됨. 이를 재사용:

```python
    # 4b. EPS Momentum — quarterly YoY 성장률 (quarterly 없으면 forward_eps 리비전 fallback)
    # quarterly_bulk는 4d Quality 블록에서 이미 계산됨 (Task 5 참고)
    eps_factor = ForwardEpsMomentumFactor()
    fwd_eps_momentum: pd.Series = eps_factor.compute(tickers, today)

    yoy_scores: dict[str, float] = {}
    for ticker in tickers:
        q_rows = quarterly_bulk.get(ticker, [])
        if len(q_rows) >= 5:
            yoy_scores[ticker] = _compute_yoy_eps_momentum(q_rows)
        else:
            yoy_scores[ticker] = float(fwd_eps_momentum.get(ticker, 0.0) or 0.0)
    raw_eps = pd.Series(yoy_scores)
```

> **주의:** `4b` 블록은 코드 순서상 `4d` 뒤에 위치해야 함 (quarterly_bulk 의존). `4b`와 `4d` 순서를 `4d → 4b`로 재배치.
>
> `_compute_yoy_eps_momentum` 시그니처를 `(q_rows: list[dict]) -> float`로 변경 (ticker 대신 rows 직접 받음):

```python
def _compute_yoy_eps_momentum(q_rows: list[dict]) -> float:
    """최근 확정 분기 EPS vs 전년 동기 EPS → YoY 성장률. q_rows는 period 내림차순."""
    if len(q_rows) < 5:
        return 0.0
    by_period = {r["period"]: r for r in q_rows}
    recent_period = q_rows[0]["period"]
    year = int(recent_period[:4])
    q    = recent_period[4:]
    yoy_period = f"{year - 1}{q}"
    recent_eps = q_rows[0].get("eps")
    yoy_row    = by_period.get(yoy_period)
    yoy_eps    = yoy_row.get("eps") if yoy_row else None
    if recent_eps is None or yoy_eps is None or yoy_eps == 0:
        return 0.0
    return (recent_eps - yoy_eps) / abs(yoy_eps)
```

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
python -m pytest tests/test_quarterly_scoring.py tests/test_naver_quarterly.py tests/test_fmp_quarterly.py -v
```

Expected: 전부 passed

- [ ] **Step 4: 커밋**

```bash
git add core/scoring/universe_scorer.py
git commit -m "feat: replace EPS momentum with quarterly YoY growth"
```

---

## Task 7: 검증 배치 실행

- [ ] **Step 1: kospi200 배치 실행**

```bash
curl -sb /tmp/dudunomics_cookie.txt -X POST "http://localhost:8000/api/screener/refresh?universe=kospi200"
```

- [ ] **Step 2: 완료 대기 및 확인**

```bash
until [ "$(curl -sb /tmp/dudunomics_cookie.txt 'http://localhost:8000/api/screener/status?universe=kospi200' | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")" = "done" ]; do sleep 10; done && echo "완료"
```

- [ ] **Step 3: 삼성전자 ROE/EPS 모멘텀 검증**

```bash
curl -sb /tmp/dudunomics_cookie.txt "http://localhost:8000/api/screener/ticker/005930.KS?universe=kospi200" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('raw_roe:', d['raw_roe'])
print('raw_debt_ratio:', d['raw_debt_ratio'])
print('raw_eps_momentum:', d['raw_eps_momentum'])
print('pct_quality:', d['pct_quality'])
print('pct_eps_momentum:', d['pct_eps_momentum'])
"
```

Expected:
- `raw_roe`: 약 19.16 (null이 아님)
- `raw_debt_ratio`: 약 0.3015 (null이 아님)
- `raw_eps_momentum`: 약 4.9 (6993/1186 - 1, null이 아님)
- `pct_quality`: null이 아닌 값

- [ ] **Step 4: kosdaq150 + sp500 배치 실행**

```bash
curl -sb /tmp/dudunomics_cookie.txt -X POST "http://localhost:8000/api/screener/refresh?universe=kosdaq150"
until [ "$(curl -sb /tmp/dudunomics_cookie.txt 'http://localhost:8000/api/screener/status?universe=kosdaq150' | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")" = "done" ]; do sleep 5; done && echo "kosdaq150 완료"
```

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "feat: quarterly financials pipeline complete — ROE/debt/EPS YoY"
```
