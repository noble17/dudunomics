# Finviz Bulk + 종목 상세 차트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FMP quarterly 호출 제거 후 Finviz bulk로 대체하고, 종목 상세 페이지에 성장성 바 차트와 주가 흐름 차트(EMA + 주가&EPS) 두 섹션을 추가한다.

**Architecture:**
- Feature A: `finviz_screener.py`가 Finviz 스크리너를 ~20회 요청으로 전 종목 EPS Q/Q를 일괄 수집. `universe_scorer.py`에서 FMP quarterly sync를 제거하고 이 값으로 `raw_eps_momentum`을 채운다.
- Feature B/C: `stockanalysis_financials.py`가 stockanalysis.com에서 연간 재무(실적+예상)를 스크래핑. `stock_detail.py` 라우터가 `/financials`와 `/price-chart` 엔드포인트를 제공. 프론트엔드는 recharts 기반 `GrowthChart`와 `PriceChart` 컴포넌트로 표시.

**Tech Stack:** FastAPI, DuckDB(SQLAlchemy), httpx+selectolax(스크래핑), SQLite(24h 캐시), React+recharts(프론트엔드), pandas(EMA 계산)

---

## 파일 구조

### 신규
- `core/data/finviz_screener.py` — Finviz screener bulk fetch (EPS Q/Q)
- `core/data/stockanalysis_financials.py` — stockanalysis.com 연간 재무 스크래퍼 + SQLite 캐시
- `api/routers/stock_detail.py` — `/financials`, `/price-chart` 엔드포인트
- `frontend/components/screener/growth-chart.tsx` — 성장성 바 차트 (3탭)
- `frontend/components/screener/price-chart.tsx` — 주가 흐름 차트 (2탭)
- `tests/test_finviz_screener.py`
- `tests/test_stockanalysis_financials.py`
- `tests/test_stock_detail_api.py`

### 수정
- `core/scoring/universe_scorer.py` — FMP quarterly 호출 제거, Finviz bulk 연동
- `api/main.py` — stock_detail 라우터 등록
- `frontend/app/screener/[ticker]/page.tsx` — 두 섹션 추가
- `frontend/lib/api.ts` — `screenerApi.financials()`, `screenerApi.priceChart()` 추가
- `frontend/lib/types.ts` — `FinancialsData`, `PriceChartData` 인터페이스 추가

---

## Task 1: Finviz Screener Bulk Fetcher

**파일:**
- Create: `core/data/finviz_screener.py`
- Test: `tests/test_finviz_screener.py`

- [ ] **Step 1: 실제 Finviz screener URL 확인 (수동)**

브라우저 또는 curl로 아래 URL 응답 확인:
```
https://finviz.com/screener.ashx?v=111&f=idx_sp500&o=ticker&r=1
```
HTML 테이블 헤더에 `EPS Q/Q` 컬럼 존재 여부 확인.
- `EPS Q/Q` 있으면 → `v=111` 사용
- 없으면 → `v=152` (커스텀뷰, 로그인 필요) 대신 `v=161` (Financial view) 시도

이 플랜은 `v=111`에 `EPS Q/Q` 있다고 가정하고 진행한다.

- [ ] **Step 2: 실패 테스트 작성**

```python
# tests/test_finviz_screener.py
from unittest.mock import patch, MagicMock


def _make_page(tickers_epsqq: list[tuple[str, str]]) -> MagicMock:
    """Finviz screener HTML 응답 mock. (ticker, eps_q_q) 쌍 목록으로 구성."""
    rows_html = ""
    for ticker, eps_qq in tickers_epsqq:
        rows_html += f"""
        <tr>
          <td class="screener-body-table-nw">1</td>
          <td class="screener-body-table-nw"><a class="screener-link-primary">{ticker}</a></td>
          <td class="screener-body-table-nw">Tech Company</td>
          <td class="screener-body-table-nw">Technology</td>
          <td class="screener-body-table-nw">USA</td>
          <td class="screener-body-table-nw">300B</td>
          <td class="screener-body-table-nw">28.50</td>
          <td class="screener-body-table-nw">26.10</td>
          <td class="screener-body-table-nw">2.50</td>
          <td class="screener-body-table-nw">8.40</td>
          <td class="screener-body-table-nw">42.30</td>
          <td class="screener-body-table-nw">0.55</td>
          <td class="screener-body-table-nw">0.24</td>
          <td class="screener-body-table-nw">6.56</td>
          <td class="screener-body-table-nw">15.00%</td>
          <td class="screener-body-table-nw">12.00%</td>
          <td class="screener-body-table-nw">{eps_qq}</td>
        </tr>"""
    html = f"""<html><body>
      <table id="screener-views-table">
        <tr>
          <th>No.</th><th>Ticker</th><th>Company</th><th>Sector</th>
          <th>Industry</th><th>Country</th><th>Market Cap</th>
          <th>P/E</th><th>Fwd P/E</th><th>PEG</th><th>P/S</th><th>P/B</th>
          <th>P/Cash</th><th>P/Free Cash Flow</th><th>Dividend</th>
          <th>Payout Ratio</th><th>EPS this Y</th><th>EPS next Y</th>
          <th>EPS past 5Y</th><th>EPS next 5Y</th><th>Sales past 5Y</th>
          <th>EPS Q/Q</th>
        </tr>
        {rows_html}
      </table>
      <span class="count-text">Total: <b>2</b> #1</span>
    </body></html>"""
    m = MagicMock()
    m.status_code = 200
    m.text = html
    return m


def test_fetch_finviz_bulk_basic(monkeypatch):
    from core.data import finviz_screener
    with patch.object(finviz_screener._CLIENT, "get") as mock_get:
        mock_get.return_value = _make_page([("AAPL", "15.23%"), ("MSFT", "-3.50%")])
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert "AAPL" in result
    assert abs(result["AAPL"]["eps_qq"] - 0.1523) < 0.001
    assert abs(result["MSFT"]["eps_qq"] - (-0.035)) < 0.001


def test_fetch_finviz_bulk_handles_dash(monkeypatch):
    from core.data import finviz_screener
    with patch.object(finviz_screener._CLIENT, "get") as mock_get:
        mock_get.return_value = _make_page([("TSLA", "-")])
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert result["TSLA"]["eps_qq"] is None


def test_fetch_finviz_bulk_paginates(monkeypatch):
    """두 번째 페이지도 fetch하는지 확인."""
    from core.data import finviz_screener
    page1 = _make_page([("AAPL", "10%")] * 25)
    # 두 번째 페이지: 1종목만 (마지막 페이지)
    page2 = _make_page([("ZZZZ", "5%")])
    call_count = 0

    def _side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch.object(finviz_screener._CLIENT, "get", side_effect=_side_effect):
        result = finviz_screener.fetch_finviz_bulk("idx_sp500")
    assert call_count == 2
    assert "ZZZZ" in result
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics
uv run pytest tests/test_finviz_screener.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError` 또는 `ImportError` (파일 미존재)

- [ ] **Step 4: `core/data/finviz_screener.py` 구현**

```python
"""core/data/finviz_screener.py — Finviz 스크리너 bulk fetch.

Finviz screener v=111 (overview)에서 EPS Q/Q를 일괄 수집.
25종목씩 페이지네이션. ~20 requests로 S&P 500 전체 커버.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_BASE = "https://finviz.com/screener.ashx"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_CLIENT = httpx.Client(http2=True, headers=_HEADERS, timeout=15, follow_redirects=True)


def _parse_pct(s: str) -> Optional[float]:
    """'15.23%' → 0.1523, '-3.50%' → -0.035, '-' → None"""
    s = s.strip()
    if not s or s == "-":
        return None
    s = s.replace("%", "")
    try:
        return float(s) / 100.0
    except ValueError:
        return None


def _parse_page(html: str) -> tuple[list[dict], int]:
    """HTML → (rows, total_count). rows: [{"ticker": ..., "eps_qq": ...}]"""
    tree = HTMLParser(html)
    rows = []

    # 헤더 컬럼 인덱스 탐색
    header_row = tree.css_first("table#screener-views-table tr")
    if not header_row:
        return rows, 0
    headers = [th.text(strip=True) for th in header_row.css("th")]
    try:
        eps_qq_idx = headers.index("EPS Q/Q")
        ticker_idx = headers.index("Ticker")
    except ValueError:
        log.warning("Finviz screener: EPS Q/Q 또는 Ticker 컬럼 없음. headers=%s", headers)
        return rows, 0

    # 데이터 행 파싱
    for tr in tree.css("table#screener-views-table tr")[1:]:
        tds = tr.css("td")
        if len(tds) <= max(ticker_idx, eps_qq_idx):
            continue
        ticker_td = tds[ticker_idx]
        ticker = ticker_td.text(strip=True)
        if not ticker or ticker.isdigit():
            continue
        eps_qq_text = tds[eps_qq_idx].text(strip=True)
        rows.append({"ticker": ticker, "eps_qq": _parse_pct(eps_qq_text)})

    # 총 종목 수 파싱 (페이지네이션 종료 조건)
    count_el = tree.css_first("span.count-text b")
    total = 0
    if count_el:
        try:
            total = int(count_el.text(strip=True).replace(",", ""))
        except ValueError:
            pass

    return rows, total


def fetch_finviz_bulk(index_filter: str = "idx_sp500") -> dict[str, dict]:
    """Finviz 스크리너에서 전 종목 EPS Q/Q 일괄 수집.

    Returns: {ticker: {"eps_qq": float | None}}
    index_filter: "idx_sp500", "idx_ndx100", "idx_dji" 등
    """
    result: dict[str, dict] = {}
    offset = 1
    total = None

    while True:
        url = f"{_BASE}?v=111&f={index_filter}&o=ticker&r={offset}"
        try:
            resp = _CLIENT.get(url)
            resp.raise_for_status()
        except Exception as e:
            log.warning("Finviz bulk fetch 실패 (r=%d): %s", offset, e)
            break

        rows, page_total = _parse_page(resp.text)
        if not rows:
            break

        for row in rows:
            result[row["ticker"]] = {"eps_qq": row["eps_qq"]}

        if total is None:
            total = page_total

        offset += 25
        if total and offset > total:
            break

    log.info("[finviz_bulk] %s: %d종목 수집", index_filter, len(result))
    return result
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_finviz_screener.py -v
```
Expected: 3개 PASS

- [ ] **Step 6: 커밋**

```bash
git add core/data/finviz_screener.py tests/test_finviz_screener.py
git commit -m "feat: Finviz screener bulk EPS Q/Q fetcher"
```

---

## Task 2: universe_scorer.py — FMP quarterly 제거 + Finviz bulk 연동

**파일:**
- Modify: `core/scoring/universe_scorer.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_finviz_screener.py 에 추가

def test_universe_scorer_uses_finviz_bulk(monkeypatch):
    """run_batch가 _sync_quarterly(FMP) 대신 Finviz bulk를 호출하는지 확인."""
    import pandas as pd
    from datetime import date
    from unittest.mock import MagicMock, patch

    # Finviz bulk 반환값
    finviz_data = {"AAPL": {"eps_qq": 0.15}, "MSFT": {"eps_qq": -0.03}}

    with patch("core.scoring.universe_scorer.get_tickers", return_value=["AAPL", "MSFT"]), \
         patch("core.scoring.universe_scorer.fetch_ohlcv", return_value=(pd.DataFrame(), [])), \
         patch("core.scoring.universe_scorer.fetch_extended", return_value=[]), \
         patch("core.scoring.universe_scorer.fetch_finviz_bulk", return_value=finviz_data) as mock_bulk, \
         patch("core.scoring.universe_scorer.repo.get_quarterly_bulk", return_value={}), \
         patch("core.scoring.universe_scorer.repo.upsert_quant_scores"), \
         patch("core.scoring.universe_scorer.PriceMomentumFactor") as MockPMF, \
         patch("core.scoring.universe_scorer.ForwardEpsMomentumFactor") as MockFEMF, \
         patch("core.scoring.universe_scorer.TechnicalFactor") as MockTF, \
         patch("core.scoring.universe_scorer.compute_valuation_zscore", return_value=pd.Series({"AAPL": 0.5, "MSFT": 0.5})), \
         patch("core.scoring.universe_scorer.bs") as mock_bs:
        MockPMF.return_value.compute.return_value = pd.Series({"AAPL": 0.1, "MSFT": 0.2})
        MockFEMF.return_value.compute.return_value = pd.Series({"AAPL": 0.1, "MSFT": 0.2})
        MockTF.compute_raw = MagicMock(return_value={"rsi": 50.0, "above_ma200": True})
        mock_bs.get.return_value = {}
        mock_bs.start = MagicMock()
        mock_bs.update = MagicMock()
        mock_bs.finish = MagicMock()

        from core.scoring import universe_scorer
        import importlib; importlib.reload(universe_scorer)
        universe_scorer.run_batch("sp500")

    mock_bulk.assert_called_once_with("idx_sp500")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_finviz_screener.py::test_universe_scorer_uses_finviz_bulk -v
```
Expected: `FAILED` (fetch_finviz_bulk 아직 import 안 됨)

- [ ] **Step 3: universe_scorer.py 수정**

`core/scoring/universe_scorer.py` 상단 import에 추가:
```python
from core.data.finviz_screener import fetch_finviz_bulk
```

`_sync_quarterly` 함수 전체를 아래로 교체 (한국 전용으로 축소):
```python
def _sync_quarterly_korean(tickers: list[str], bs_universe: str | None = None) -> None:
    """국내 종목 전용 분기 재무 sync (Naver). 해외는 Finviz bulk로 대체."""
    import core.batch_state as _bs
    from core.data.naver_quarterly import fetch_naver_quarterly as _fetch

    total = len(tickers)
    latest_in_db = repo.get_latest_quarterly_period(tickers)
    rows_to_upsert: list[dict] = []
    for i, ticker in enumerate(tickers, 1):
        if bs_universe:
            _bs.update(bs_universe, f"분기 재무 동기화 중 ({i}/{total})", i)
        fetched = _fetch(ticker)
        if not fetched:
            continue
        api_latest = fetched[0]["period"]
        db_latest = latest_in_db.get(ticker)
        if db_latest and db_latest >= api_latest:
            continue
        rows_to_upsert.extend(fetched)
    if rows_to_upsert:
        repo.upsert_quarterly_financials(rows_to_upsert)
        log.info("[quarterly sync] %d행 upsert (korean)", len(rows_to_upsert))
```

`run_batch` 함수에서 `_sync_quarterly` 호출 부분(line ~113-115) 교체:

기존:
```python
    # 3b. 분기 재무 sync (append-only)
    log.info("[Universe Scorer] 분기 재무 sync 중...")
    _sync_quarterly(tickers, universe, bs_universe=universe)
```

교체:
```python
    # 3b. 분기 재무 sync: 한국은 Naver, 해외는 Finviz bulk
    is_korean = universe in ("kospi200", "kosdaq150")
    if is_korean:
        log.info("[Universe Scorer] 분기 재무 sync 중 (Naver)...")
        _sync_quarterly_korean(tickers, bs_universe=universe)

    # 3c. Finviz bulk — 해외 유니버스 EPS Q/Q 일괄 수집
    finviz_index_map = {"sp500": "idx_sp500", "nasdaq100": "idx_ndx100"}
    finviz_bulk_data: dict[str, dict] = {}
    if not is_korean and universe in finviz_index_map:
        log.info("[Universe Scorer] Finviz bulk 수집 중...")
        bs.update(universe, "Finviz bulk 수집 중", 0)
        finviz_bulk_data = fetch_finviz_bulk(finviz_index_map[universe])
```

`run_batch`의 EPS 계산 구간(line ~159-170) 교체:

기존:
```python
    yoy_scores: dict[str, float] = {}
    for ticker in tickers:
        q_rows = quarterly_bulk.get(ticker, [])
        if len(q_rows) >= 5:
            yoy_scores[ticker] = _compute_yoy_eps_momentum(q_rows)
        else:
            yoy_scores[ticker] = float(fwd_eps_momentum.get(ticker, 0.0) or 0.0)
    raw_eps = pd.Series(yoy_scores)
```

교체:
```python
    yoy_scores: dict[str, float] = {}
    for ticker in tickers:
        # 해외: Finviz bulk EPS Q/Q 우선
        if not is_korean and ticker in finviz_bulk_data:
            v = finviz_bulk_data[ticker].get("eps_qq")
            yoy_scores[ticker] = float(v) if v is not None else 0.0
            continue
        # 국내: quarterly_financials YoY 우선
        q_rows = quarterly_bulk.get(ticker, [])
        if len(q_rows) >= 5:
            yoy_scores[ticker] = _compute_yoy_eps_momentum(q_rows)
        else:
            yoy_scores[ticker] = float(fwd_eps_momentum.get(ticker, 0.0) or 0.0)
    raw_eps = pd.Series(yoy_scores)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_finviz_screener.py -v
```
Expected: 4개 PASS

- [ ] **Step 5: 커밋**

```bash
git add core/scoring/universe_scorer.py tests/test_finviz_screener.py
git commit -m "feat: FMP quarterly 제거, Finviz bulk EPS Q/Q 연동"
```

---

## Task 3: StockAnalysis 연간 재무 스크래퍼

**파일:**
- Create: `core/data/stockanalysis_financials.py`
- Test: `tests/test_stockanalysis_financials.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_stockanalysis_financials.py
from unittest.mock import patch, MagicMock


def _make_forecast_html(ticker="AAPL") -> str:
    """stockanalysis.com /stocks/AAPL/forecast/ 응답 mock HTML."""
    return """<html><body>
    <table data-testid="financial-table" data-feature="revenue">
      <thead><tr><th></th><th>2021</th><th>2022</th><th>2023</th><th>2024</th><th>2025E</th><th>2026E</th></tr></thead>
      <tbody>
        <tr><td>Revenue</td><td>365,817</td><td>394,328</td><td>383,285</td><td>391,035</td><td>415,200</td><td>438,000</td></tr>
      </tbody>
    </table>
    <table data-testid="financial-table" data-feature="eps">
      <thead><tr><th></th><th>2021</th><th>2022</th><th>2023</th><th>2024</th><th>2025E</th><th>2026E</th></tr></thead>
      <tbody>
        <tr><td>EPS</td><td>5.61</td><td>6.11</td><td>6.13</td><td>6.09</td><td>7.20</td><td>8.05</td></tr>
      </tbody>
    </table>
    <p>Last earnings report: <span>May 26, 2026</span></p>
    </body></html>"""


def test_fetch_annual_financials_revenue(monkeypatch):
    from core.data import stockanalysis_financials as sa
    with patch.object(sa._CLIENT, "get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=_make_forecast_html())
        result = sa.fetch_annual_financials("AAPL")
    assert len(result["revenue"]) == 6
    fy2024 = next(r for r in result["revenue"] if r["year"] == "2024")
    assert fy2024["value"] == 391035
    assert fy2024["is_estimate"] is False
    fy2025 = next(r for r in result["revenue"] if r["year"] == "2025")
    assert fy2025["is_estimate"] is True


def test_fetch_annual_financials_eps(monkeypatch):
    from core.data import stockanalysis_financials as sa
    with patch.object(sa._CLIENT, "get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, text=_make_forecast_html())
        result = sa.fetch_annual_financials("AAPL")
    fy2024 = next(r for r in result["eps"] if r["year"] == "2024")
    assert abs(fy2024["value"] - 6.09) < 0.01


def test_korean_ticker_returns_none(monkeypatch):
    from core.data import stockanalysis_financials as sa
    result = sa.fetch_annual_financials("005930.KS")
    assert result is None


def test_cache_hit_skips_http(monkeypatch, tmp_path):
    from core.data import stockanalysis_financials as sa
    # 캐시 DB를 tmp_path에 설정
    monkeypatch.setattr(sa, "_DB_PATH", tmp_path / "sa_cache.sqlite")
    import time
    # 캐시에 직접 쓰기
    data = {"revenue": [{"year": "2024", "period_end": "2024.09", "value": 391035, "is_estimate": False}],
            "eps": [], "roe": [], "latest_report_date": "2026.05.26"}
    sa._to_cache("AAPL", data)
    with patch.object(sa._CLIENT, "get") as mock_get:
        result = sa.fetch_annual_financials("AAPL")
    mock_get.assert_not_called()
    assert result["revenue"][0]["value"] == 391035
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_stockanalysis_financials.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `core/data/stockanalysis_financials.py` 구현**

```python
"""core/data/stockanalysis_financials.py — stockanalysis.com 연간 재무 스크래퍼.

엔드포인트: https://stockanalysis.com/stocks/{ticker}/forecast/
데이터: Revenue(백만달러), EPS, ROE(계산)
캐시: data/fundamentals_cache.sqlite 의 sa_financials 테이블, 24h TTL.
국내 종목(KS/KQ): None 반환.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "fundamentals_cache.sqlite"
_TTL = 86_400  # 24h
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; dudunomics/1.0; research use)",
    "Accept-Language": "en-US,en;q=0.9",
}
_SKIP_SUFFIXES = (".KS", ".KQ", ".T", ".HK", ".SS", ".SZ")

_CLIENT = httpx.Client(http2=True, headers=_HEADERS, timeout=15, follow_redirects=True)


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sa_financials "
        "(ticker TEXT PRIMARY KEY, data TEXT, ts REAL)"
    )
    conn.commit()
    return conn


def _from_cache(ticker: str) -> Optional[dict]:
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT data, ts FROM sa_financials WHERE ticker=?", (ticker,)
        ).fetchone()
        conn.close()
        if row and time.time() - row[1] < _TTL:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _to_cache(ticker: str, data: dict) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO sa_financials VALUES (?, ?, ?)",
            (ticker, json.dumps(data), time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _parse_num(s: str) -> Optional[float]:
    s = s.strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "N/A", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_table(tree: HTMLParser, feature: str) -> list[dict]:
    """data-feature='{feature}' 테이블 파싱 → [{year, period_end, value, is_estimate}]"""
    table = tree.css_first(f'table[data-feature="{feature}"]')
    if not table:
        return []

    headers = [th.text(strip=True) for th in table.css("thead th")][1:]  # 첫 열 제거
    data_row = None
    for tr in table.css("tbody tr"):
        cells = tr.css("td")
        if cells:
            data_row = cells
            break
    if not data_row:
        return []

    values = data_row[1:]  # 첫 열(라벨) 제거
    result = []
    for i, (header, td) in enumerate(zip(headers, values)):
        is_estimate = header.endswith("E")
        year = header.rstrip("E")
        val = _parse_num(td.text(strip=True))
        if val is None:
            continue
        result.append({
            "year": year,
            "period_end": year,  # 실제 회계연도 종료월은 추후 보완 가능
            "value": val,
            "is_estimate": is_estimate,
        })
    return result


def _parse_latest_report_date(tree: HTMLParser) -> Optional[str]:
    """'Last earnings report: May 26, 2026' → '2026.05.26'"""
    for p in tree.css("p"):
        text = p.text(strip=True)
        if "Last earnings" in text or "earnings report" in text.lower():
            span = p.css_first("span")
            if span:
                import datetime
                try:
                    dt = datetime.datetime.strptime(span.text(strip=True), "%B %d, %Y")
                    return dt.strftime("%Y.%m.%d")
                except ValueError:
                    pass
    return None


def fetch_annual_financials(ticker: str) -> Optional[dict]:
    """연간 재무 데이터 반환. 국내 종목은 None. 캐시 우선.

    Returns: {
        "revenue":  [{"year", "period_end", "value", "is_estimate"}, ...],
        "eps":      [...],
        "roe":      [],  # 현재 미구현 (balance sheet 별도 스크래핑 필요)
        "latest_report_date": "YYYY.MM.DD" | None,
    }
    """
    if any(ticker.upper().endswith(s) for s in _SKIP_SUFFIXES):
        return None

    cached = _from_cache(ticker)
    if cached:
        return cached

    try:
        url = f"https://stockanalysis.com/stocks/{ticker.lower()}/forecast/"
        resp = _CLIENT.get(url)
        resp.raise_for_status()
    except Exception as e:
        log.debug("stockanalysis fetch 실패 (%s): %s", ticker, e)
        return None

    tree = HTMLParser(resp.text)
    revenue = _parse_table(tree, "revenue")
    eps = _parse_table(tree, "eps")
    latest_date = _parse_latest_report_date(tree)

    data = {
        "revenue": revenue,
        "eps": eps,
        "roe": [],
        "latest_report_date": latest_date,
    }
    _to_cache(ticker, data)
    return data
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_stockanalysis_financials.py -v
```
Expected: 4개 PASS

- [ ] **Step 5: 커밋**

```bash
git add core/data/stockanalysis_financials.py tests/test_stockanalysis_financials.py
git commit -m "feat: stockanalysis.com 연간 재무 스크래퍼 (Revenue, EPS)"
```

---

## Task 4: 백엔드 stock_detail 라우터

**파일:**
- Create: `api/routers/stock_detail.py`
- Modify: `api/main.py`
- Test: `tests/test_stock_detail_api.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_stock_detail_api.py
from unittest.mock import patch
from datetime import date


def test_financials_endpoint_returns_data(client):
    """GET /api/screener/ticker/AAPL/financials 정상 응답 확인."""
    mock_data = {
        "revenue": [{"year": "2024", "period_end": "2024.09", "value": 391035, "is_estimate": False}],
        "eps": [{"year": "2024", "period_end": "2024.09", "value": 6.09, "is_estimate": False}],
        "roe": [],
        "latest_report_date": "2026.05.26",
    }
    with patch("api.routers.stock_detail.fetch_annual_financials", return_value=mock_data):
        resp = client.get("/api/screener/ticker/AAPL/financials?universe=sp500")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revenue"][0]["value"] == 391035
    assert body["latest_report_date"] == "2026.05.26"
    assert "metrics" in body


def test_financials_404_for_unknown(client):
    with patch("api.routers.stock_detail.fetch_annual_financials", return_value=None):
        resp = client.get("/api/screener/ticker/ZZZZ/financials?universe=sp500")
    assert resp.status_code == 404


def test_price_chart_endpoint_returns_data(client):
    """GET /api/screener/ticker/AAPL/price-chart 정상 응답 확인."""
    import pandas as pd
    import numpy as np

    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    mock_df = pd.DataFrame(
        {("AAPL", "Close"): np.linspace(200, 210, 10)},
        index=dates,
    )

    with patch("api.routers.stock_detail.fetch_ohlcv", return_value=(mock_df, [])), \
         patch("api.routers.stock_detail.repo.get_quarterly_financials", return_value=[
             {"period": "2025Q1", "eps": 1.57}
         ]):
        resp = client.get("/api/screener/ticker/AAPL/price-chart")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["ohlcv"]) == 10
    assert "ema" in body
    assert "e5" in body["ema"]
    assert "e20" in body["ema"]
    assert "e60" in body["ema"]
    assert len(body["quarterly_eps"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/test_stock_detail_api.py -v 2>&1 | head -20
```
Expected: `FAILED` (라우터 미존재)

- [ ] **Step 3: `api/routers/stock_detail.py` 구현**

```python
"""api/routers/stock_detail.py — 종목 상세 재무/차트 엔드포인트."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from core.auth.deps import current_user, CurrentUser
from core.data.stockanalysis_financials import fetch_annual_financials
from core.data.fundamentals_scraper import fetch_fundamentals
from core.data.ohlcv_cache import fetch_ohlcv
import core.repository as repo

router = APIRouter(prefix="/api/screener/ticker", tags=["stock-detail"])


@router.get("/{ticker}/financials")
def get_financials(
    ticker: str,
    universe: str = "sp500",
    user: CurrentUser = Depends(current_user),
):
    """연간 재무 데이터 (Revenue, EPS, ROE) + 밸류에이션 메트릭."""
    upper = ticker.upper()
    data = fetch_annual_financials(upper)
    if data is None:
        raise HTTPException(status_code=404, detail=f"{upper} 재무 데이터 없음 (국내 종목 미지원)")

    # fundamentals_scraper 캐시에서 밸류에이션 메트릭 조회 (24h 캐시, Finviz 기반)
    snap = fetch_fundamentals(upper)
    metrics: dict = {
        "market_cap_m": snap.market_cap_m if snap else None,
        "trailing_pe": snap.trailing_pe if snap else None,
        "forward_pe": snap.forward_pe if snap else None,
        "peg": snap.peg if snap else None,
        "price_to_sales": snap.price_to_sales if snap else None,
    }

    return {
        "revenue": data["revenue"],
        "eps": data["eps"],
        "roe": data["roe"],
        "latest_report_date": data.get("latest_report_date"),
        "metrics": metrics,
    }


def _compute_ema(series: pd.Series, span: int) -> list[dict]:
    ema = series.ewm(span=span, adjust=False).mean()
    return [
        {"date": str(d.date()), "value": round(float(v), 4)}
        for d, v in ema.items()
        if not pd.isna(v)
    ]


@router.get("/{ticker}/price-chart")
def get_price_chart(
    ticker: str,
    user: CurrentUser = Depends(current_user),
):
    """주가 OHLCV + EMA(5/20/60) + 분기 EPS."""
    upper = ticker.upper()
    today = date.today()
    start = today - timedelta(days=380)

    df, _ = fetch_ohlcv([upper], start, today)
    if df.empty or (upper, "Close") not in df.columns:
        raise HTTPException(status_code=404, detail=f"{upper} OHLCV 데이터 없음")

    close = df[(upper, "Close")].dropna()

    ohlcv_list = [
        {"date": str(d.date()), "close": round(float(v), 4)}
        for d, v in close.items()
    ]

    quarterly_rows = repo.get_quarterly_financials(upper, n=12)
    quarterly_eps = [
        {
            "period": r["period"],
            "date": _period_to_date(r["period"]),
            "eps": r.get("eps"),
            "is_estimate": False,
        }
        for r in quarterly_rows
        if r.get("eps") is not None
    ]

    return {
        "ohlcv": ohlcv_list,
        "ema": {
            "e5": _compute_ema(close, 5),
            "e20": _compute_ema(close, 20),
            "e60": _compute_ema(close, 60),
        },
        "quarterly_eps": quarterly_eps,
    }


def _period_to_date(period: str) -> str:
    """'2025Q1' → '2025-03-31', '2025Q2' → '2025-06-30', etc."""
    _ends = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
    year = period[:4]
    q = period[4:]
    return f"{year}-{_ends.get(q, '12-31')}"
```

- [ ] **Step 4: `api/main.py`에 라우터 등록**

`api/main.py`의 import 블록 끝에 추가:
```python
from api.routers.stock_detail import router as stock_detail_router
```

`app.include_router(trades_router)` 다음 줄에 추가:
```python
app.include_router(stock_detail_router)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_stock_detail_api.py -v
```
Expected: 3개 PASS

- [ ] **Step 6: 커밋**

```bash
git add api/routers/stock_detail.py api/main.py tests/test_stock_detail_api.py
git commit -m "feat: /financials, /price-chart 엔드포인트 추가"
```

---

## Task 5: 프론트엔드 타입 + API 클라이언트

**파일:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: `frontend/lib/types.ts`에 인터페이스 추가**

파일 끝에 아래 추가:
```typescript
export interface FinancialDataPoint {
  year: string;
  period_end: string;
  value: number;
  is_estimate: boolean;
}

export interface FinancialMetrics {
  market_cap_m: number | null;
  trailing_pe: number | null;
  forward_pe: number | null;
  peg: number | null;
  price_to_sales: number | null;
}

export interface FinancialsData {
  revenue: FinancialDataPoint[];
  eps: FinancialDataPoint[];
  roe: FinancialDataPoint[];
  latest_report_date: string | null;
  metrics: FinancialMetrics;
}

export interface OhlcvPoint {
  date: string;
  close: number;
}

export interface EmaPoint {
  date: string;
  value: number;
}

export interface QuarterlyEpsPoint {
  period: string;
  date: string;
  eps: number;
  is_estimate: boolean;
}

export interface PriceChartData {
  ohlcv: OhlcvPoint[];
  ema: {
    e5: EmaPoint[];
    e20: EmaPoint[];
    e60: EmaPoint[];
  };
  quarterly_eps: QuarterlyEpsPoint[];
}
```

- [ ] **Step 2: `frontend/lib/api.ts`의 `screenerApi`에 메서드 추가**

`screenerApi` 객체 안에 기존 `upsertNote` 다음에 추가:
```typescript
  financials: (ticker: string, universe = "sp500") =>
    request<FinancialsData>(`/api/screener/ticker/${ticker}/financials?universe=${universe}`),
  priceChart: (ticker: string) =>
    request<PriceChartData>(`/api/screener/ticker/${ticker}/price-chart`),
```

- [ ] **Step 3: import 추가 확인**

`frontend/lib/api.ts` 상단 import에 `FinancialsData`, `PriceChartData` 추가:
```typescript
import type {
  // ... 기존 타입들 ...
  FinancialsData,
  PriceChartData,
} from "./types";
```

- [ ] **Step 4: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 에러 없음

- [ ] **Step 5: 커밋**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat: FinancialsData, PriceChartData 타입 및 API 클라이언트 추가"
```

---

## Task 6: GrowthChart 컴포넌트 (성장성 바 차트)

**파일:**
- Create: `frontend/components/screener/growth-chart.tsx`

- [ ] **Step 1: `growth-chart.tsx` 구현**

```tsx
// frontend/components/screener/growth-chart.tsx
"use client";

import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { FinancialsData, FinancialDataPoint } from "@/lib/types";

interface Props {
  data: FinancialsData;
}

type Tab = "revenue" | "eps" | "roe";

const TABS: { key: Tab; label: string; unit: string }[] = [
  { key: "revenue", label: "매출액", unit: "백만달러" },
  { key: "eps",     label: "EPS 주당순이익", unit: "달러" },
  { key: "roe",     label: "ROE", unit: "%" },
];

function fmtValue(value: number, tab: Tab): string {
  if (tab === "revenue") {
    return value >= 1_000 ? `${(value / 1_000).toFixed(0)}B` : `${value.toFixed(0)}M`;
  }
  if (tab === "eps") return `$${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

export function GrowthChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("revenue");
  const tabCfg = TABS.find((t) => t.key === activeTab)!;
  const points: FinancialDataPoint[] = data[activeTab] ?? [];

  const chartData = points.map((p) => ({
    name: p.period_end || p.year,
    value: p.value,
    is_estimate: p.is_estimate,
  }));

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      {/* 섹션 헤더 */}
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        성장성과 수익성 흐름은?
      </p>

      {/* 탭 */}
      <div className="flex gap-1 mb-3">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              activeTab === t.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 우상단 메타 */}
      <div className="flex justify-between text-xs text-muted-foreground mb-2">
        <span className="bg-blue-100 text-blue-700 rounded px-2 py-0.5 text-[10px]">연간</span>
        {data.latest_report_date && (
          <span>최근실적발표 {data.latest_report_date} · 단위: {tabCfg.unit}</span>
        )}
      </div>

      {/* 바 차트 */}
      {chartData.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
          데이터 없음
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              formatter={(v: number) => fmtValue(v, activeTab)}
              contentStyle={{ fontSize: 11, borderRadius: 6 }}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={40}>
              <LabelList
                dataKey="value"
                position="top"
                formatter={(v: number) => fmtValue(v, activeTab)}
                style={{ fontSize: 10, fill: "var(--foreground)" }}
              />
              {chartData.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.is_estimate ? "var(--muted)" : "var(--color-chart-1, #3b82f6)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* 하단 메트릭 */}
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs border-t border-border pt-3">
        {data.metrics.market_cap_m !== null && (
          <div className="col-span-2 flex justify-between">
            <span className="text-muted-foreground">시가총액</span>
            <span className="font-mono font-semibold">
              {data.metrics.market_cap_m.toLocaleString()} 백만달러
            </span>
          </div>
        )}
        {[
          { label: "PER", value: data.metrics.trailing_pe, suffix: "배" },
          { label: "PER(F)", value: data.metrics.forward_pe, suffix: "배" },
          { label: "PEG", value: data.metrics.peg, suffix: "배" },
          { label: "PSR", value: data.metrics.price_to_sales, suffix: "배" },
        ].map(({ label, value, suffix }) => (
          <div key={label} className="flex justify-between">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono">{value !== null ? `${value?.toFixed(2)}${suffix}` : "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/screener/growth-chart.tsx
git commit -m "feat: GrowthChart 성장성 바 차트 컴포넌트"
```

---

## Task 7: PriceChart 컴포넌트 (주가 흐름 차트)

**파일:**
- Create: `frontend/components/screener/price-chart.tsx`

- [ ] **Step 1: `price-chart.tsx` 구현**

```tsx
// frontend/components/screener/price-chart.tsx
"use client";

import { useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { PriceChartData } from "@/lib/types";

interface Props {
  data: PriceChartData;
}

type Tab = "ema" | "price_eps";

// YY.MM 형식
function fmtDate(dateStr: string): string {
  const d = new Date(dateStr);
  const yy = String(d.getFullYear()).slice(2);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${yy}.${mm}`;
}

// 3개월치 기준 필터
function last3Months(points: { date: string }[]): typeof points {
  if (points.length === 0) return points;
  const latest = new Date(points[points.length - 1].date);
  const cutoff = new Date(latest);
  cutoff.setMonth(cutoff.getMonth() - 3);
  return points.filter((p) => new Date(p.date) >= cutoff);
}

export function PriceChart({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("ema");
  const [emaRange, setEmaRange] = useState<"short" | "full">("short");

  const emaPoints = emaRange === "short" ? last3Months(data.ema.e5) : data.ema.e5;
  const emaIndexSet = new Set(emaPoints.map((p) => p.date));

  const emaChartData = data.ohlcv
    .filter((p) => emaIndexSet.has(p.date))
    .map((p) => {
      const e5 = data.ema.e5.find((e) => e.date === p.date);
      const e20 = data.ema.e20.find((e) => e.date === p.date);
      const e60 = data.ema.e60.find((e) => e.date === p.date);
      return {
        date: p.date,
        e5: e5?.value,
        e20: e20?.value,
        e60: e60?.value,
      };
    });

  const priceEpsChartData = data.ohlcv.map((p) => {
    const eps = data.quarterly_eps.find((e) => e.date <= p.date);
    return { date: p.date, price: p.close, eps: eps?.eps };
  });

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        주가 흐름은?
      </p>

      {/* 탭 */}
      <div className="flex gap-1 mb-3">
        {([["ema", "지수이동평균선(EMA)"], ["price_eps", "주가&EPS"]] as [Tab, string][]).map(
          ([key, label]) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                activeTab === key
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {label}
            </button>
          )
        )}
      </div>

      {activeTab === "ema" && (
        <>
          <div className="flex gap-1 mb-2">
            {(["short", "full"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setEmaRange(r)}
                className={`px-2 py-0.5 text-[10px] rounded ${
                  emaRange === r ? "bg-muted-foreground text-background" : "text-muted-foreground"
                }`}
              >
                {r === "short" ? "단기(3M)" : "중기(전체)"}
              </button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={emaChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false} tickLine={false} width={50}
              />
              <Tooltip
                formatter={(v: number) => `$${v.toFixed(2)}`}
                labelFormatter={fmtDate}
                contentStyle={{ fontSize: 11, borderRadius: 6 }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11 }}
                formatter={(v) => ({ e5: "EMA5", e20: "EMA20", e60: "EMA60" }[v] ?? v)}
              />
              <Line type="monotone" dataKey="e5" stroke="#22c55e" dot={false} strokeWidth={1.5} name="e5" />
              <Line type="monotone" dataKey="e20" stroke="#9ca3af" dot={false} strokeWidth={1.5} name="e20" />
              <Line type="monotone" dataKey="e60" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="e60" />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}

      {activeTab === "price_eps" && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={priceEpsChartData} margin={{ top: 4, right: 50, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => {
                const dt = new Date(d);
                return `${dt.getFullYear()}.${String(dt.getMonth() + 1).padStart(2, "0")}`;
              }}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false} tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              yAxisId="price"
              domain={["auto", "auto"]}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false} tickLine={false} width={50}
            />
            <YAxis
              yAxisId="eps"
              orientation="right"
              domain={["auto", "auto"]}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false} tickLine={false} width={40}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 6 }}
              formatter={(v: number, name: string) =>
                name === "price" ? [`$${v.toFixed(2)}`, "주가"] : [`$${v.toFixed(2)}`, "EPS"]
              }
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(v) => (v === "price" ? "● 주가" : "● 주당순이익")}
            />
            <Line
              yAxisId="price" type="monotone" dataKey="price"
              stroke="#3b82f6" dot={false} strokeWidth={1.5} name="price"
            />
            <Line
              yAxisId="eps" type="stepAfter" dataKey="eps"
              stroke="#22c55e" dot={false} strokeWidth={2} name="eps"
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/screener/price-chart.tsx
git commit -m "feat: PriceChart EMA + 주가&EPS 차트 컴포넌트"
```

---

## Task 8: 종목 상세 페이지 통합

**파일:**
- Modify: `frontend/app/screener/[ticker]/page.tsx`

- [ ] **Step 1: page.tsx 수정**

`frontend/app/screener/[ticker]/page.tsx` 상단 import에 추가:
```tsx
import useSWR from "swr";
import { GrowthChart } from "@/components/screener/growth-chart";
import { PriceChart } from "@/components/screener/price-chart";
import type { FinancialsData, PriceChartData } from "@/lib/types";
```

(기존 `import useSWR from "swr"` 제거 후 합치거나, 아래 두 줄만 추가)

`TickerDetailPage` 함수 안에서 기존 `const { data: score, isLoading }` 선언 다음에 추가:
```tsx
  const { data: financials } = useSWR<FinancialsData>(
    ticker ? `/api/screener/ticker/${ticker}/financials` : null,
    () => screenerApi.financials(ticker, universe),
    { shouldRetryOnError: false }
  );

  const { data: priceChart } = useSWR<PriceChartData>(
    ticker ? `/api/screener/ticker/${ticker}/price-chart` : null,
    () => screenerApi.priceChart(ticker),
    { shouldRetryOnError: false }
  );
```

기존 `{score && (` JSX 블록의 맨 끝 `</div>` 바로 위(NoteForm div 이후)에 두 섹션 추가:

기존 코드 찾기 (page.tsx line ~112):
```tsx
      )}
    </div>
  );
}
```

교체:
```tsx
      {/* 성장성 차트 */}
      {financials && (
        <GrowthChart data={financials} />
      )}

      {/* 주가 흐름 차트 */}
      {priceChart && (
        <PriceChart data={priceChart} />
      )}
      )}
    </div>
  );
}
```

실제 삽입 위치는 `score && (` 블록 전체의 종료 `)}` 바로 앞, 즉 `{score && (...)}` 이후이다. 정확한 위치:

```tsx
      {/* 기존 score 섹션 끝 */}
      )}

      {/* 성장성 차트 */}
      {financials && (
        <GrowthChart data={financials} />
      )}

      {/* 주가 흐름 차트 */}
      {priceChart && (
        <PriceChart data={priceChart} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/app/screener/[ticker]/page.tsx
git commit -m "feat: 종목 상세 페이지에 성장성/주가 흐름 차트 섹션 추가"
```

---

## Task 9: 전체 테스트 + 브라우저 검증

- [ ] **Step 1: 전체 백엔드 테스트**

```bash
cd /Users/user/Development/private/dudunomics
uv run pytest tests/test_finviz_screener.py tests/test_stockanalysis_financials.py tests/test_stock_detail_api.py -v
```
Expected: 전부 PASS

- [ ] **Step 2: 기존 테스트 회귀 확인**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: 실패 없음 (또는 기존에 이미 skip 처리된 것만 fail)

- [ ] **Step 3: 개발 서버 실행 + 브라우저 확인**

```bash
# 백엔드
uv run uvicorn api.main:app --reload --port 8765 &

# 프론트엔드
cd frontend && npm run dev
```

브라우저에서 `/screener/AAPL` 접근:
- [ ] 성장성 차트 섹션 렌더링 확인
- [ ] 3탭(매출액/EPS/ROE) 전환 확인
- [ ] 하단 메트릭 표시 확인
- [ ] 주가 흐름 섹션 렌더링 확인
- [ ] EMA탭 단기/중기 토글 확인
- [ ] 주가&EPS 탭 이중축 차트 확인

---

## 스펙 커버리지 체크

| 요구사항 | 구현 태스크 |
|---|---|
| A. FMP quarterly sync 제거 (US) | Task 2 |
| A. Finviz bulk EPS Q/Q → raw_eps_momentum | Task 1, 2 |
| A. 국내 Naver quarterly 유지 | Task 2 |
| B. /financials 엔드포인트 | Task 4 |
| B. Revenue/EPS 바 차트 | Task 6 |
| B. 3탭 + 하단 메트릭 | Task 6 |
| B. stockanalysis.com 스크래퍼 | Task 3 |
| B. SQLite 24h 캐시 | Task 3 |
| C. /price-chart 엔드포인트 | Task 4 |
| C. EMA(5/20/60) 라인 | Task 7 |
| C. 주가&EPS 이중축 | Task 7 |
| C. 단기/중기 토글 | Task 7 |
| 페이지 통합 | Task 8 |

### 미결 사항 (구현 전 확인 필요)
1. **Finviz v=111 EPS Q/Q 컬럼**: Task 1 Step 1에서 수동 확인 필요. 컬럼명이 다르면 `_parse_page` 수정.
2. **국내 종목 차트**: stockanalysis.com 미지원 → 현재 구현은 404 반환 + 프론트엔드 미표시. 추후 naver 연동 시 확장 가능.
3. **quant_scores에 raw_market_cap 컬럼**: Task 4에서 `score.get("raw_market_cap")` 사용. 실제 컬럼명이 다를 경우 `market_cap_m` 등으로 수정 필요.
