# Valuation Overhaul — EV/EBITDA 통합 밸류에이션 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 밸류에이션 스코어를 PBR+PER에서 EV/EBITDA+PER로 전환하고, 자본잠식 플래그·FCF Yield·PEG·섹터 필터를 추가한다.

**Architecture:** Finviz 스냅샷 파싱 확장(EV/EBITDA, PEG, Market Cap, Sector) → StockAnalysis CapEx 추가 수집 → ExtendedSnapshot 전달 → universe_scorer에서 EV/EBITDA+PER z-score 계산 → DB + API 노출. yfinance는 완전 제거.

**Tech Stack:** Python 3.12, httpx + selectolax (스크래핑), DuckDB (메인 DB), SQLite (fundamentals 캐시), FastAPI + Pydantic, pytest

---

## 파일 변경 목록

| 파일 | 역할 |
|------|------|
| `core/data/fundamentals_scraper.py` | Finviz + StockAnalysis 파싱 확장 (신규 필드 7개) |
| `core/data/fundamentals_extended.py` | ExtendedSnapshot 확장, yfinance 제거, fcf_yield 계산 |
| `core/factors/valuation.py` | EV/EBITDA+PER 통합 함수로 교체 |
| `core/scoring/universe_scorer.py` | 밸류에이션 분기 로직 교체 + 신규 raw 컬럼 |
| `core/repository.py` | quant_scores 마이그레이션 + upsert 업데이트 |
| `api/models.py` | QuantScoreOut 신규 필드 추가 |
| `tests/test_valuation.py` | 기존 PBR 테스트 교체 + DELL 시나리오 추가 |

---

## Task 1: DB 스키마 마이그레이션

**Files:**
- Modify: `core/repository.py:232-246` (마이그레이션 목록), `core/repository.py:728-766` (upsert)

- [ ] **Step 1: 마이그레이션 목록에 신규 컬럼 추가**

`core/repository.py`의 migration 리스트(기존 마지막 항목 바로 뒤)에 추가:

```python
# 기존:
"CREATE INDEX IF NOT EXISTS idx_quant_scores_uni_date ON quant_scores (universe, as_of)",

# 아래 항목들을 이 줄 뒤에 추가:
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_ev_ebitda      DOUBLE",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_peg            DOUBLE",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_fcf_yield      DOUBLE",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS raw_eps_momentum   DOUBLE",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS negative_book_value BOOLEAN DEFAULT FALSE",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS sector             TEXT",
"ALTER TABLE quant_scores ADD COLUMN IF NOT EXISTS industry           TEXT",
```

- [ ] **Step 2: `upsert_quant_scores` INSERT 컬럼·VALUES·UPDATE SET 확장**

`core/repository.py:728-766`의 `upsert_quant_scores` 함수를 아래로 교체:

```python
def upsert_quant_scores(rows: list[dict]) -> None:
    if not rows:
        return
    with session() as s:
        for r in rows:
            s.execute(text("""
                INSERT INTO quant_scores
                    (ticker, universe, as_of,
                     pct_momentum, pct_valuation, pct_eps_momentum, pct_quality, pct_technical,
                     raw_momentum, raw_fwd_pe, raw_pbr, raw_psr, raw_trailing_pe,
                     raw_eps_ttm, raw_fwd_eps, raw_roe, raw_debt_ratio, raw_rsi,
                     above_ma200, cfo_positive, company_name,
                     raw_ev_ebitda, raw_peg, raw_fcf_yield, raw_eps_momentum,
                     negative_book_value, sector, industry)
                VALUES
                    (:ticker, :universe, :as_of,
                     :pct_momentum, :pct_valuation, :pct_eps_momentum, :pct_quality, :pct_technical,
                     :raw_momentum, :raw_fwd_pe, :raw_pbr, :raw_psr, :raw_trailing_pe,
                     :raw_eps_ttm, :raw_fwd_eps, :raw_roe, :raw_debt_ratio, :raw_rsi,
                     :above_ma200, :cfo_positive, :company_name,
                     :raw_ev_ebitda, :raw_peg, :raw_fcf_yield, :raw_eps_momentum,
                     :negative_book_value, :sector, :industry)
                ON CONFLICT (ticker, universe, as_of) DO UPDATE SET
                    pct_momentum = excluded.pct_momentum,
                    pct_valuation = excluded.pct_valuation,
                    pct_eps_momentum = excluded.pct_eps_momentum,
                    pct_quality = excluded.pct_quality,
                    pct_technical = excluded.pct_technical,
                    raw_momentum = excluded.raw_momentum,
                    raw_fwd_pe = excluded.raw_fwd_pe,
                    raw_pbr = excluded.raw_pbr,
                    raw_psr = excluded.raw_psr,
                    raw_trailing_pe = excluded.raw_trailing_pe,
                    raw_eps_ttm = excluded.raw_eps_ttm,
                    raw_fwd_eps = excluded.raw_fwd_eps,
                    raw_roe = excluded.raw_roe,
                    raw_debt_ratio = excluded.raw_debt_ratio,
                    raw_rsi = excluded.raw_rsi,
                    above_ma200 = excluded.above_ma200,
                    cfo_positive = excluded.cfo_positive,
                    company_name = excluded.company_name,
                    raw_ev_ebitda = excluded.raw_ev_ebitda,
                    raw_peg = excluded.raw_peg,
                    raw_fcf_yield = excluded.raw_fcf_yield,
                    raw_eps_momentum = excluded.raw_eps_momentum,
                    negative_book_value = excluded.negative_book_value,
                    sector = excluded.sector,
                    industry = excluded.industry
            """), r)
        s.commit()
```

- [ ] **Step 3: 마이그레이션 실행 확인**

```bash
cd /Users/user/Development/private/dudunomics
uv run python -c "import core.repository as r; r.init_db(); print('OK')"
```

Expected: `OK` 출력, 에러 없음

- [ ] **Step 4: 신규 컬럼 존재 확인**

```bash
uv run python -c "
import core.repository as repo
from sqlalchemy import text
with repo.session() as s:
    cols = s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='quant_scores'\")).fetchall()
    names = [c[0] for c in cols]
    for expected in ['raw_ev_ebitda','raw_peg','raw_fcf_yield','raw_eps_momentum','negative_book_value','sector','industry']:
        assert expected in names, f'Missing: {expected}'
    new_cols = ['raw_ev_ebitda','raw_peg','raw_fcf_yield','raw_eps_momentum','negative_book_value','sector','industry']
    print('All columns present:', [n for n in names if n in new_cols])
"
```

Expected: `All columns present: [...]` 출력

- [ ] **Step 5: 커밋**

```bash
git add core/repository.py
git commit -m "feat: quant_scores에 EV/EBITDA·PEG·FCF·섹터 컬럼 추가"
```

---

## Task 2: FundamentalsSnapshot — Finviz 신규 필드 파싱

**Files:**
- Modify: `core/data/fundamentals_scraper.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_fundamentals_scraper.py` 파일이 없으면 생성, 있으면 아래 추가:

```python
"""tests/test_fundamentals_scraper.py"""


def test_parse_market_cap_m_billions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("45.2B") == pytest.approx(45_200.0)


def test_parse_market_cap_m_trillions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("1.05T") == pytest.approx(1_050_000.0)


def test_parse_market_cap_m_millions():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("250.00M") == pytest.approx(250.0)


def test_parse_market_cap_m_none():
    from core.data.fundamentals_scraper import _parse_market_cap_m
    assert _parse_market_cap_m("") is None
    assert _parse_market_cap_m("-") is None


def test_negative_book_value_detection(monkeypatch):
    """Finviz P/B = '-' → negative_book_value=True, price_to_book=None"""
    from core.data.fundamentals_scraper import _fetch_finviz
    import httpx

    html = """
    <table class="snapshot-table2">
      <tr><td>P/E</td><td>12.5</td><td>P/B</td><td>-</td>
          <td>EV/EBITDA</td><td>8.5</td><td>PEG</td><td>0.8</td>
          <td>Market Cap</td><td>45.2B</td><td>Sector</td><td>Technology</td>
          <td>Industry</td><td>Computer Hardware</td></tr>
    </table>
    """

    class FakeResponse:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr("core.data.fundamentals_scraper._CLIENT", type("C", (), {"get": lambda self, u: FakeResponse()})())

    snap = _fetch_finviz("DELL")
    assert snap.negative_book_value is True
    assert snap.price_to_book is None
    assert snap.ev_ebitda == pytest.approx(8.5)
    assert snap.peg == pytest.approx(0.8)
    assert snap.market_cap_m == pytest.approx(45_200.0)
    assert snap.sector == "Technology"
    assert snap.industry == "Computer Hardware"


import pytest
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_fundamentals_scraper.py -v 2>&1 | head -30
```

Expected: `ImportError` 또는 `AttributeError` — `_parse_market_cap_m` 미존재

- [ ] **Step 3: FundamentalsSnapshot 신규 필드 추가**

`core/data/fundamentals_scraper.py`의 `FundamentalsSnapshot` 데이터클래스에 필드 추가:

```python
@dataclass
class FundamentalsSnapshot:
    ticker: str
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    return_on_equity: Optional[float] = None
    debt_to_equity: Optional[float] = None
    operating_cashflow: Optional[float] = None
    short_name: Optional[str] = None
    # 신규
    ev_ebitda: Optional[float] = None
    peg: Optional[float] = None
    market_cap_m: Optional[float] = None   # 단위: 백만 USD
    capex: Optional[float] = None          # 절댓값 (양수 저장), 단위: USD
    sector: Optional[str] = None
    industry: Optional[str] = None
    negative_book_value: bool = False
```

- [ ] **Step 4: `_parse_market_cap_m` 헬퍼 추가**

`_parse_num` 함수 바로 아래에 추가:

```python
def _parse_market_cap_m(s: str) -> Optional[float]:
    """Market Cap 문자열 → 백만 USD 단위 float. 예: '45.2B' → 45200.0"""
    if not s:
        return None
    s = s.strip().replace(",", "")
    for suffix, mult in [("T", 1_000_000), ("B", 1_000), ("M", 1), ("K", 0.001)]:
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except ValueError:
                return None
    try:
        return float(s) / 1_000_000
    except ValueError:
        return None
```

- [ ] **Step 5: `_fetch_finviz` 파싱 로직 업데이트**

`_fetch_finviz` 내부의 기존 파싱 블록을 아래로 교체 (`snap.forward_pe = ...` 부터 `snap.debt_to_equity = ...` 까지):

```python
        snap.forward_pe = _parse_num(kv.get("Forward P/E", ""))
        snap.trailing_pe = _parse_num(kv.get("P/E", ""))
        # P/B: "-"이면 자본잠식 플래그, 아니면 파싱
        raw_pb = kv.get("P/B", "").strip()
        if raw_pb == "-":
            snap.negative_book_value = True
            snap.price_to_book = None
        else:
            snap.price_to_book = _parse_num(raw_pb)
            snap.negative_book_value = False
        snap.price_to_sales = _parse_num(kv.get("P/S", ""))
        snap.forward_eps = _parse_num(kv.get("EPS next Y", ""))
        snap.trailing_eps = _parse_num(kv.get("EPS", ""))
        snap.return_on_equity = _parse_num(kv.get("ROE", ""))
        snap.debt_to_equity = _parse_num(kv.get("Debt/Eq", ""))
        # 신규 필드
        snap.ev_ebitda = _parse_num(kv.get("EV/EBITDA", ""))
        snap.peg = _parse_num(kv.get("PEG", ""))
        snap.market_cap_m = _parse_market_cap_m(kv.get("Market Cap", ""))
        snap.sector = kv.get("Sector") or None
        snap.industry = kv.get("Industry") or None
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
uv run pytest tests/test_fundamentals_scraper.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add core/data/fundamentals_scraper.py tests/test_fundamentals_scraper.py
git commit -m "feat: Finviz에서 EV/EBITDA·PEG·MarketCap·섹터·자본잠식플래그 파싱"
```

---

## Task 3: StockAnalysis — CapEx 파싱 추가

**Files:**
- Modify: `core/data/fundamentals_scraper.py:132-156` (`_supplement_stockanalysis`)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_fundamentals_scraper.py`에 추가:

```python
def test_supplement_stockanalysis_capex(monkeypatch):
    """StockAnalysis CF 표에서 CapEx를 절댓값으로 파싱"""
    from core.data.fundamentals_scraper import _supplement_stockanalysis, FundamentalsSnapshot
    import httpx

    html = """
    <table>
      <tr><td>Operating Cash Flow</td><td>5.0B</td></tr>
      <tr><td>Capital Expenditures</td><td>-1.2B</td></tr>
    </table>
    """

    class FakeResponse:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr("core.data.fundamentals_scraper._CLIENT", type("C", (), {"get": lambda self, u: FakeResponse()})())

    snap = FundamentalsSnapshot(ticker="DELL")
    _supplement_stockanalysis(snap)
    assert snap.operating_cashflow == pytest.approx(5_000_000_000)
    assert snap.capex == pytest.approx(1_200_000_000)  # 절댓값 (양수)
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_fundamentals_scraper.py::test_supplement_stockanalysis_capex -v
```

Expected: FAIL — `assert snap.capex == ...` (capex는 None)

- [ ] **Step 3: `_supplement_stockanalysis` 교체**

`core/data/fundamentals_scraper.py`의 `_supplement_stockanalysis` 함수 전체를 교체:

```python
def _supplement_stockanalysis(snap: FundamentalsSnapshot) -> None:
    """Fill in missing operating_cashflow and capex from stockanalysis.com."""
    if snap.operating_cashflow is not None and snap.capex is not None:
        return
    try:
        url = f"https://stockanalysis.com/stocks/{snap.ticker.lower()}/financials/cash-flow-statement/"
        r = _CLIENT.get(url)
        r.raise_for_status()
        tree = HTMLParser(r.text)

        def _parse_cf_value(raw: str) -> Optional[float]:
            raw = raw.strip()
            # 괄호로 묶인 음수 처리: "(1.2B)" → "-1.2B"
            if raw.startswith("(") and raw.endswith(")"):
                raw = "-" + raw[1:-1]
            for suffix, exp in (("T", "e12"), ("B", "e9"), ("M", "e6"), ("K", "e3")):
                if raw.endswith(suffix):
                    raw = raw[:-1] + exp
                    break
            return _parse_num(raw)

        for row in tree.css("tr"):
            cells = row.css("td")
            if not cells:
                continue
            label = cells[0].text(strip=True).lower()
            value = cells[1].text(strip=True) if len(cells) > 1 else ""

            if snap.operating_cashflow is None and "operating" in label and "cash" in label:
                snap.operating_cashflow = _parse_cf_value(value)

            if snap.capex is None and (
                "capital expenditure" in label
                or "capex" in label
                or ("purchase" in label and "property" in label)
            ):
                v = _parse_cf_value(value)
                snap.capex = abs(v) if v is not None else None  # 절댓값으로 저장

            if snap.operating_cashflow is not None and snap.capex is not None:
                break
    except Exception as e:
        log.debug("stockanalysis supplement failed for %s: %s", snap.ticker, e)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_fundamentals_scraper.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add core/data/fundamentals_scraper.py tests/test_fundamentals_scraper.py
git commit -m "feat: StockAnalysis에서 CapEx 파싱 추가 (FCF 계산용)"
```

---

## Task 4: ExtendedSnapshot 확장 + yfinance 제거

**Files:**
- Modify: `core/data/fundamentals_extended.py` (전체)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_fundamentals_extended.py` 생성:

```python
"""tests/test_fundamentals_extended.py"""
import pytest
from datetime import date
from unittest.mock import patch, MagicMock


def _make_scraped(**kwargs):
    from core.data.fundamentals_scraper import FundamentalsSnapshot
    defaults = dict(
        ticker="DELL",
        forward_pe=12.0,
        trailing_pe=14.0,
        price_to_book=None,
        price_to_sales=0.5,
        forward_eps=8.5,
        trailing_eps=7.0,
        return_on_equity=None,
        debt_to_equity=300.0,
        operating_cashflow=5_000_000_000,
        short_name="Dell Technologies",
        ev_ebitda=8.5,
        peg=0.8,
        market_cap_m=45_000.0,
        capex=1_200_000_000,
        sector="Technology",
        industry="Computer Hardware",
        negative_book_value=True,
    )
    defaults.update(kwargs)
    return FundamentalsSnapshot(**defaults)


def test_fcf_yield_computed():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped()
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    # fcf = 5B - 1.2B = 3.8B, market_cap = 45_000M * 1e6 = 45B
    # fcf_yield = 3.8B / 45B ≈ 0.0844
    assert snap.fcf_yield is not None
    assert pytest.approx(snap.fcf_yield, abs=0.001) == 3_800_000_000 / (45_000 * 1_000_000)


def test_negative_book_value_propagated():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped(negative_book_value=True, price_to_book=None)
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    assert snap.negative_book_value is True
    assert snap.pbr is None


def test_fcf_yield_none_when_capex_missing():
    from core.data.fundamentals_extended import _fetch_one
    scraped = _make_scraped(capex=None)
    with patch("core.data.fundamentals_extended._scrape", return_value=scraped):
        snap = _fetch_one("DELL", date.today())
    assert snap.fcf_yield is None


def test_no_yfinance_import():
    """yfinance가 fundamentals_extended에서 임포트되지 않아야 함"""
    import ast, pathlib
    src = pathlib.Path("core/data/fundamentals_extended.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any("yfinance" in n for n in names), "yfinance import found!"
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_fundamentals_extended.py -v 2>&1 | head -30
```

Expected: FAIL — `ExtendedSnapshot` 에 `fcf_yield` 등 미존재

- [ ] **Step 3: `fundamentals_extended.py` 전체 교체**

`core/data/fundamentals_extended.py`를 아래 내용으로 교체:

```python
"""확장 펀더멘탈 스냅샷 — EV/EBITDA, FCF Yield, PEG, 섹터 포함.

1차: fundamentals_scraper (Finviz + StockAnalysis) → 실패 시 빈 스냅샷 반환.
yfinance 의존성 없음.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from core.data.fundamentals_scraper import fetch_fundamentals as _scrape

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtendedSnapshot:
    ticker: str
    as_of: date
    company_name: str | None = None
    # 밸류에이션
    forward_pe: float | None = None
    trailing_pe: float | None = None
    pbr: float | None = None
    psr: float | None = None
    ev_ebitda: float | None = None       # EV/EBITDA
    peg: float | None = None             # PEG (5yr expected)
    market_cap_m: float | None = None    # 시가총액, 백만 USD
    # 현금흐름
    operating_cashflow: float | None = None
    capex: float | None = None           # 절댓값 (양수)
    fcf_yield: float | None = None       # (OCF - CapEx) / 시가총액
    # 어닝스
    forward_eps: float | None = None
    eps_ttm: float | None = None
    # 퀄리티
    roe: float | None = None
    debt_to_equity: float | None = None
    # 자본잠식
    negative_book_value: bool = False
    # 섹터
    sector: str | None = None
    industry: str | None = None
    error: str | None = field(default=None, hash=False, compare=False)


def _compute_fcf_yield(ocf: float | None, capex: float | None, market_cap_m: float | None) -> float | None:
    if ocf is None or capex is None or not market_cap_m or market_cap_m <= 0:
        return None
    market_cap = market_cap_m * 1_000_000
    return (ocf - capex) / market_cap


def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    t_upper = ticker.upper()
    if t_upper.endswith(".KS") or t_upper.endswith(".KQ"):
        return ExtendedSnapshot(ticker=ticker, as_of=as_of)

    scraped = _scrape(ticker)
    if scraped is None:
        return ExtendedSnapshot(ticker=ticker, as_of=as_of, error="scrape_failed")

    return ExtendedSnapshot(
        ticker=ticker,
        as_of=as_of,
        company_name=scraped.short_name or ticker,
        forward_pe=scraped.forward_pe,
        trailing_pe=scraped.trailing_pe,
        pbr=scraped.price_to_book,
        psr=scraped.price_to_sales,
        ev_ebitda=scraped.ev_ebitda if (scraped.ev_ebitda is not None and scraped.ev_ebitda > 0) else None,
        peg=scraped.peg,
        market_cap_m=scraped.market_cap_m,
        operating_cashflow=scraped.operating_cashflow,
        capex=scraped.capex,
        fcf_yield=_compute_fcf_yield(scraped.operating_cashflow, scraped.capex, scraped.market_cap_m),
        forward_eps=scraped.forward_eps,
        eps_ttm=scraped.trailing_eps,
        roe=scraped.return_on_equity,
        debt_to_equity=scraped.debt_to_equity,
        negative_book_value=scraped.negative_book_value,
        sector=scraped.sector,
        industry=scraped.industry,
    )


def fetch_extended(
    tickers: list[str],
    max_workers: int = 1,
    progress_callback=None,
) -> list[ExtendedSnapshot]:
    """순차 페치. progress_callback(done, total): 각 티커 완료 후 호출."""
    from datetime import date as dt_date
    today = dt_date.today()
    results: list[ExtendedSnapshot] = []
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        if i % 50 == 0:
            log.info("[fundamentals] %d/%d 완료", i, total)
        results.append(_fetch_one(ticker, today))
        if progress_callback:
            progress_callback(i, total)
    return results
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_fundamentals_extended.py -v
```

Expected: 모든 테스트 PASS (`test_no_yfinance_import` 포함)

- [ ] **Step 5: 커밋**

```bash
git add core/data/fundamentals_extended.py tests/test_fundamentals_extended.py
git commit -m "feat: ExtendedSnapshot 확장 + yfinance 제거 + FCF Yield 계산"
```

---

## Task 5: valuation.py — EV/EBITDA+PER 통합 함수

**Files:**
- Modify: `core/factors/valuation.py` (전체 교체)
- Modify: `tests/test_valuation.py` (기존 PBR 테스트 교체)

- [ ] **Step 1: 기존 테스트를 새 API로 교체**

`tests/test_valuation.py`를 아래 내용으로 교체:

```python
"""tests/test_valuation.py"""
import numpy as np
import pandas as pd
import pytest


def test_winsorize_clips_outliers():
    from core.factors.valuation import _winsorize_series
    data = list(range(1, 101)) + [1000.0]
    s = pd.Series(data)
    result = _winsorize_series(s, limits=(0.01, 0.01))
    assert result.max() < 1000.0


def test_zscore_series_mean_zero():
    from core.factors.valuation import _zscore_series
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    result = _zscore_series(s)
    assert abs(result.mean()) < 1e-9


def test_zscore_series_rank_fallback_on_zero_std():
    from core.factors.valuation import _zscore_series
    s = pd.Series([5.0, 5.0, 5.0])
    result = _zscore_series(s)
    assert result is not None  # crash하지 않음


def test_compute_valuation_zscore_uses_ev_ebitda():
    """EV/EBITDA 있으면 60% 가중치 적용"""
    from core.factors.valuation import compute_valuation_zscore
    # A: 낮은 EV/EBITDA + 낮은 PER = 저평가
    # C: 높은 EV/EBITDA + 높은 PER = 고평가
    ev = pd.Series({"A": 5.0,  "B": 15.0, "C": 30.0})
    pe = pd.Series({"A": 10.0, "B": 20.0, "C": 35.0})
    result = compute_valuation_zscore(ev, pe)
    assert result["A"] < result["C"]


def test_compute_valuation_zscore_fallback_to_per_only():
    """EV/EBITDA 없으면 PER 단독 z-score"""
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series(dtype=float)   # 빈 Series
    pe = pd.Series({"A": 10.0, "B": 20.0, "C": 30.0})
    result = compute_valuation_zscore(ev, pe)
    assert result["A"] < result["B"] < result["C"]


def test_compute_valuation_zscore_partial_ev_ebitda():
    """EV/EBITDA 있는 종목은 결합, 없는 종목(자본잠식 등)은 PER 단독"""
    from core.factors.valuation import compute_valuation_zscore
    ev = pd.Series({"A": 8.0, "B": 20.0})          # C는 EV/EBITDA 없음
    pe = pd.Series({"A": 10.0, "B": 25.0, "C": 12.0})
    result = compute_valuation_zscore(ev, pe)
    assert "C" in result.index       # PER 단독으로 포함되어야 함
    assert "A" in result.index
    assert result.notna().all()


def test_dell_scenario():
    """DELL: negative_book_value=True, EV/EBITDA=8.5 → 정상 계산"""
    from core.factors.valuation import compute_valuation_zscore
    # 유니버스 대비 DELL이 저평가여야 함 (낮은 EV/EBITDA + 낮은 PER)
    ev = pd.Series({"DELL": 8.5, "AAPL": 22.0, "MSFT": 28.0, "AMZN": 35.0, "META": 18.0})
    pe = pd.Series({"DELL": 12.0, "AAPL": 28.0, "MSFT": 32.0, "AMZN": 45.0, "META": 22.0})
    result = compute_valuation_zscore(ev, pe)
    # DELL이 유니버스에서 가장 낮은 z-score (=가장 저평가)
    assert result["DELL"] == result.min()
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_valuation.py -v 2>&1 | head -30
```

Expected: FAIL — `ImportError: cannot import name 'compute_valuation_zscore'`

- [ ] **Step 3: `valuation.py` 전체 교체**

`core/factors/valuation.py`를 아래 내용으로 교체:

```python
"""core/factors/valuation.py — EV/EBITDA + PER 통합 밸류에이션 팩터.

EV/EBITDA(60%) + Forward PER(40%) Winsorize → Z-score 합산.
EV/EBITDA 없는 종목(자본잠식, 데이터 누락)은 PER 단독 z-score.
낮을수록 저평가이므로 백분위 계산 시 ascending=False.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import ClassVar

import pandas as pd
from scipy.stats.mstats import winsorize

from core.factors.base import Factor

log = logging.getLogger(__name__)


def _winsorize_series(s: pd.Series, limits=(0.01, 0.01)) -> pd.Series:
    """NaN 제외 후 윈저라이징, NaN은 원위치 복원."""
    mask = s.notna()
    result = s.copy()
    result[mask] = winsorize(s[mask].values, limits=limits)
    return result


def _zscore_series(s: pd.Series) -> pd.Series:
    """Z-score. std ≈ 0이면 rank 기반 fallback [-1, 1]."""
    std = s.std()
    if std < 1e-6:
        log.warning("Z-score std≈0 — rank fallback 사용")
        return s.rank(pct=True) * 2 - 1
    return (s - s.mean()) / std


def compute_valuation_zscore(
    ev_ebitda: pd.Series,
    fwd_pe: pd.Series,
) -> pd.Series:
    """EV/EBITDA + PER → 통합 밸류에이션 z-score.

    - EV/EBITDA 있는 종목: 0.6 × EV/EBITDA_z + 0.4 × PER_z
    - EV/EBITDA 없는 종목: PER_z 단독
    낮을수록 저평가 (백분위 변환 시 ascending=False).
    """
    pe_clean = fwd_pe.dropna()
    if pe_clean.empty:
        return pd.Series(dtype=float)

    w_pe = _winsorize_series(pe_clean)
    z_pe = _zscore_series(w_pe)

    ev_clean = ev_ebitda.dropna()
    if ev_clean.empty:
        return z_pe.reindex(fwd_pe.index)

    w_ev = _winsorize_series(ev_clean)
    z_ev = _zscore_series(w_ev)

    common = z_pe.index.intersection(z_ev.index)
    pe_only = z_pe.index.difference(common)

    combined = 0.6 * z_ev[common] + 0.4 * z_pe[common]
    result = pd.concat([combined, z_pe[pe_only]])
    return result.reindex(fwd_pe.index)


class ValuationFactor(Factor):
    """배치 외부(단일 종목 조회 등)용 인터페이스. 배치는 universe_scorer 직접 사용."""
    name: ClassVar[str] = "valuation"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        from sqlalchemy import text
        import core.repository as repo
        import math

        fwd_pe: dict[str, float] = {}
        ev_ebitda: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                row = s.execute(text("""
                    SELECT raw_fwd_pe, raw_ev_ebitda FROM quant_scores
                    WHERE ticker = :t AND universe = 'sp500'
                    ORDER BY as_of DESC LIMIT 1
                """), {"t": ticker}).fetchone()
                if row:
                    if row[0] is not None and row[0] > 0:
                        fwd_pe[ticker] = row[0]
                    if row[1] is not None and row[1] > 0:
                        ev_ebitda[ticker] = row[1]

        return compute_valuation_zscore(
            pd.Series(ev_ebitda),
            pd.Series(fwd_pe),
        ).reindex(tickers)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/test_valuation.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add core/factors/valuation.py tests/test_valuation.py
git commit -m "feat: valuation 팩터를 EV/EBITDA+PER 통합 z-score로 교체 (PBR 제거)"
```

---

## Task 6: universe_scorer.py — 새 팩터 통합

**Files:**
- Modify: `core/scoring/universe_scorer.py:81-107` (밸류에이션 블록), `core/scoring/universe_scorer.py:148-173` (DB rows 블록)

- [ ] **Step 1: 밸류에이션 계산 블록 교체**

`core/scoring/universe_scorer.py`의 `# 4c. Valuation raw` 블록(81-107줄)을 교체:

```python
    # 4c. Valuation raw (EV/EBITDA + PER — Winsorize + Z-score)
    raw_fwd_pe    = pd.Series({t: snap_map[t].forward_pe for t in tickers if t in snap_map})
    raw_ev_ebitda = pd.Series({t: snap_map[t].ev_ebitda  for t in tickers if t in snap_map})

    from core.factors.valuation import compute_valuation_zscore
    raw_valuation = compute_valuation_zscore(
        raw_ev_ebitda.dropna(),
        raw_fwd_pe.dropna(),
    ).reindex(tickers)
```

- [ ] **Step 2: import 정리**

파일 상단의 import에서 `_winsorize_series`, `_combined_value_zscore` 관련 구문이 있다면 제거 (Task 5에서 함수명이 바뀌었으므로).

현재 `from core.factors.valuation import _winsorize_series, _combined_value_zscore` 줄을 삭제 (Step 1의 새 블록에서 `compute_valuation_zscore`를 직접 import).

- [ ] **Step 3: DB rows 블록에 신규 컬럼 추가**

`core/scoring/universe_scorer.py`의 `rows.append({...})` 블록(148-173줄)을 교체:

```python
    rows: list[dict] = []
    for ticker in tickers:
        snap = snap_map.get(ticker)
        rows.append({
            "ticker": ticker,
            "universe": universe,
            "as_of": today,
            "pct_momentum":     _safe_float(pct_momentum.get(ticker)),
            "pct_valuation":    _safe_float(pct_valuation.get(ticker)),
            "pct_eps_momentum": _safe_float(pct_eps.get(ticker)),
            "pct_quality":      _safe_float(pct_quality.get(ticker)),
            "pct_technical":    _safe_float(pct_technical.get(ticker)),
            "raw_momentum":     _safe_float(raw_momentum.get(ticker)),
            "raw_fwd_pe":       snap.forward_pe if snap else None,
            "raw_pbr":          snap.pbr if snap else None,
            "raw_psr":          snap.psr if snap else None,
            "raw_trailing_pe":  snap.trailing_pe if snap else None,
            "raw_eps_ttm":      snap.eps_ttm if snap else None,
            "raw_fwd_eps":      snap.forward_eps if snap else None,
            "raw_roe":          snap.roe if snap else None,
            "raw_debt_ratio":   (snap.debt_to_equity / 100.0) if (snap and snap.debt_to_equity) else None,
            "raw_rsi":          _safe_float(raw_rsi.get(ticker)),
            "above_ma200":      bool(above_ma200.get(ticker, False)),
            "cfo_positive":     bool(snap.operating_cashflow and snap.operating_cashflow > 0) if snap else False,
            "company_name":     snap.company_name if snap else None,
            # 신규
            "raw_ev_ebitda":    snap.ev_ebitda if snap else None,
            "raw_peg":          snap.peg if snap else None,
            "raw_fcf_yield":    snap.fcf_yield if snap else None,
            "negative_book_value": bool(snap.negative_book_value) if snap else False,
            "sector":           snap.sector if snap else None,
            "industry":         snap.industry if snap else None,
        })
```

- [ ] **Step 4: 타입 체크 (import 오류 없음 확인)**

```bash
uv run python -c "from core.scoring.universe_scorer import run_batch; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 5: 커밋**

```bash
git add core/scoring/universe_scorer.py
git commit -m "feat: universe_scorer EV/EBITDA+PER 밸류에이션 + 신규 raw 컬럼 통합"
```

---

## Task 7: api/models.py — QuantScoreOut 신규 필드 노출

**Files:**
- Modify: `api/models.py:161-185` (`QuantScoreOut`)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_screener_api.py`에 추가 (없으면 생성):

```python
"""tests/test_screener_api.py"""


def test_quant_score_out_has_new_fields():
    from api.models import QuantScoreOut
    from datetime import date

    row = QuantScoreOut(
        ticker="DELL",
        universe="sp500",
        as_of=date.today(),
        raw_ev_ebitda=8.5,
        raw_peg=0.8,
        raw_fcf_yield=0.084,
        negative_book_value=True,
        raw_eps_momentum=0.15,
        sector="Technology",
        industry="Computer Hardware",
    )
    assert row.pbr_flag == "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
    assert row.peg_undervalued is True
    assert row.eps_revision_up is True


def test_pbr_flag_none_for_normal_company():
    from api.models import QuantScoreOut
    from datetime import date

    row = QuantScoreOut(
        ticker="AAPL",
        universe="sp500",
        as_of=date.today(),
        raw_pbr=35.0,
        negative_book_value=False,
    )
    assert row.pbr_flag is None


def test_peg_undervalued_false_when_above_one():
    from api.models import QuantScoreOut
    from datetime import date

    row = QuantScoreOut(
        ticker="MSFT",
        universe="sp500",
        as_of=date.today(),
        raw_peg=2.5,
    )
    assert row.peg_undervalued is False
```

- [ ] **Step 2: 실패 확인**

```bash
uv run pytest tests/test_screener_api.py -v 2>&1 | head -20
```

Expected: FAIL — `QuantScoreOut` 에 `raw_ev_ebitda` 등 필드 미존재

- [ ] **Step 3: `QuantScoreOut` 확장**

`api/models.py`의 `QuantScoreOut` 클래스 전체를 교체:

```python
class QuantScoreOut(BaseModel):
    ticker: str
    universe: str
    as_of: date
    company_name: str | None = None
    # 백분위 (0~1)
    pct_momentum: float | None = None
    pct_valuation: float | None = None
    pct_eps_momentum: float | None = None
    pct_quality: float | None = None
    pct_technical: float | None = None
    # Raw 값
    raw_momentum: float | None = None
    raw_fwd_pe: float | None = None
    raw_pbr: float | None = None         # 표시 전용 (스코어링 미사용)
    raw_psr: float | None = None
    raw_trailing_pe: float | None = None
    raw_eps_ttm: float | None = None
    raw_fwd_eps: float | None = None
    raw_roe: float | None = None
    raw_debt_ratio: float | None = None
    raw_rsi: float | None = None
    above_ma200: bool | None = None
    cfo_positive: bool | None = None
    # 신규 Raw 값
    raw_ev_ebitda: float | None = None
    raw_peg: float | None = None
    raw_fcf_yield: float | None = None
    raw_eps_momentum: float | None = None
    # 섹터
    sector: str | None = None
    industry: str | None = None
    # 파생 플래그 (DB 저장 없음, 응답 시 계산)
    negative_book_value: bool = False

    @property
    def pbr_flag(self) -> str | None:
        if self.negative_book_value:
            return "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
        return None

    @property
    def peg_undervalued(self) -> bool:
        return self.raw_peg is not None and 0 < self.raw_peg < 1.0

    @property
    def eps_revision_up(self) -> bool:
        return self.raw_eps_momentum is not None and self.raw_eps_momentum > 0

    model_config = {"from_attributes": True}
```

> **주의**: Pydantic v2에서 `@property`는 응답 직렬화에 포함되지 않는다. `pbr_flag`, `peg_undervalued`, `eps_revision_up`을 JSON 응답에 포함하려면 `@computed_field`로 선언해야 한다. 아래와 같이 수정:

```python
from pydantic import BaseModel, computed_field
from datetime import date


class QuantScoreOut(BaseModel):
    ticker: str
    universe: str
    as_of: date
    company_name: str | None = None
    pct_momentum: float | None = None
    pct_valuation: float | None = None
    pct_eps_momentum: float | None = None
    pct_quality: float | None = None
    pct_technical: float | None = None
    raw_momentum: float | None = None
    raw_fwd_pe: float | None = None
    raw_pbr: float | None = None
    raw_psr: float | None = None
    raw_trailing_pe: float | None = None
    raw_eps_ttm: float | None = None
    raw_fwd_eps: float | None = None
    raw_roe: float | None = None
    raw_debt_ratio: float | None = None
    raw_rsi: float | None = None
    above_ma200: bool | None = None
    cfo_positive: bool | None = None
    raw_ev_ebitda: float | None = None
    raw_peg: float | None = None
    raw_fcf_yield: float | None = None
    raw_eps_momentum: float | None = None
    negative_book_value: bool = False
    sector: str | None = None
    industry: str | None = None

    @computed_field
    @property
    def pbr_flag(self) -> str | None:
        if self.negative_book_value:
            return "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
        return None

    @computed_field
    @property
    def peg_undervalued(self) -> bool:
        return self.raw_peg is not None and 0 < self.raw_peg < 1.0

    @computed_field
    @property
    def eps_revision_up(self) -> bool:
        return self.raw_eps_momentum is not None and self.raw_eps_momentum > 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: `raw_eps_momentum`을 universe_scorer rows에 추가**

`core/scoring/universe_scorer.py`의 rows 딕셔너리에 누락된 `raw_eps_momentum` 추가:

```python
# raw_momentum 바로 아래에 추가
"raw_eps_momentum": _safe_float(raw_eps.get(ticker)),
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/test_screener_api.py tests/test_valuation.py tests/test_fundamentals_extended.py tests/test_fundamentals_scraper.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 서버 기동 및 API 응답 확인**

```bash
uv run uvicorn api.main:app --reload --port 8000 &
sleep 3
curl -s http://localhost:8000/api/screener/scores?universe=sp500 | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data:
    first = data[0]
    for field in ['raw_ev_ebitda','raw_peg','raw_fcf_yield','negative_book_value','sector','pbr_flag','peg_undervalued','eps_revision_up']:
        print(f'{field}: {first.get(field, \"MISSING\")}')
" 2>/dev/null || echo "데이터 없음 (배치 미실행)"
```

Expected: 필드가 `MISSING` 없이 출력 (값은 None 가능)

- [ ] **Step 7: 최종 커밋**

```bash
git add api/models.py core/scoring/universe_scorer.py tests/test_screener_api.py
git commit -m "feat: API QuantScoreOut에 EV/EBITDA·FCF Yield·PEG·섹터·플래그 필드 추가"
```

---

## 전체 테스트 스위트 실행

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 기존 테스트 포함 전체 PASS

---

## 참고: 배치 실행 후 DELL 검증

배치 실행 후 DELL 데이터 확인:

```bash
curl -s "http://localhost:8000/api/screener/ticker/DELL?universe=sp500" | python3 -m json.tool | grep -E "ev_ebitda|fcf_yield|peg|negative|pbr_flag|sector|eps_revision"
```

Expected 예시:
```json
"raw_ev_ebitda": 8.5,
"raw_fcf_yield": 0.084,
"raw_peg": 0.8,
"negative_book_value": true,
"pbr_flag": "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)",
"peg_undervalued": true,
"sector": "Technology",
"eps_revision_up": true
```
