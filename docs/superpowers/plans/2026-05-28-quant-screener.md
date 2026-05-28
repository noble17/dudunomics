# Quant Screener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5팩터 동적 가중치 퀀트 스코어링 시스템 — S&P 500 유니버스 배치 계산, 종목 스크리닝 페이지(실시간 재랭킹), 종목 상세 분석 페이지(레이더 차트 + 재무 지표 + 투자 메모).

**Architecture:** 서버는 하루 1회 배치로 5팩터 백분위를 계산해 DuckDB에 저장. 프론트엔드는 최초 로드 시 전체 유니버스 데이터(~35KB)를 받아 브라우저에서 즉시 가중치 합산·재랭킹. 상세 페이지는 단일 종목 API + 투자 메모 CRUD.

**Tech Stack:** Python (scipy, yfinance, pandas), FastAPI, DuckDB/SQLAlchemy, Next.js 15, TypeScript, SWR, Tailwind CSS

---

## File Map

**신규 백엔드**
- `core/data/universe_provider.py` — S&P 500 티커 목록
- `core/data/fundamentals_extended.py` — PBR, PSR, ROE, D/E, CFO 페치
- `core/factors/price_momentum.py` — 12-1M 모멘텀
- `core/factors/valuation.py` — FWD PER + PBR (Winsorizing)
- `core/factors/quality.py` — ROE + D/E + CFO
- `core/factors/technical.py` — RSI 백분위 + 200일 MA
- `core/scoring/__init__.py` — 빈 파일
- `core/scoring/universe_scorer.py` — 배치 계산 오케스트레이터
- `api/routers/screener.py` — 스크리너 엔드포인트

**수정 백엔드**
- `core/factors/forward_eps_momentum.py` — 3M slope 추가
- `core/repository.py` — quant_scores·ticker_notes 테이블 + 인덱스 + 조회 함수
- `api/models.py` — QuantScoreOut, TickerNoteIn/Out 모델
- `api/main.py` — screener 라우터 등록
- `requirements.txt` — scipy 추가

**신규 프론트엔드**
- `frontend/lib/types.ts` — QuantScore, TickerNote, FactorWeights 타입 추가
- `frontend/lib/api.ts` — screenerApi 추가
- `frontend/app/screener/page.tsx`
- `frontend/app/screener/[ticker]/page.tsx`
- `frontend/components/screener/factor-sidebar.tsx`
- `frontend/components/screener/ranking-table.tsx`
- `frontend/components/screener/radar-chart.tsx`
- `frontend/components/screener/factor-bars.tsx`
- `frontend/components/screener/metric-grid.tsx`
- `frontend/components/screener/note-form.tsx`

**수정 프론트엔드**
- `frontend/components/nav.tsx` — "종목분석" 탭 추가

---

## Task 1: requirements.txt에 scipy 추가

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: scipy 추가**

```
# requirements.txt 기존 내용 유지, 데이터 섹션에 추가:
scipy==1.14.1
```

- [ ] **Step 2: 설치 확인**

```bash
uv pip install scipy==1.14.1
python -c "from scipy.stats.mstats import winsorize; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add scipy for winsorizing and percentile ranking"
```

---

## Task 2: DB 스키마 — quant_scores + ticker_notes + 인덱스

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: `_init_schema` DDL에 두 테이블 + 인덱스 추가**

`_init_schema` 함수 내 `ddl` 문자열 끝(마지막 `"""` 전)에 추가:

```sql
    CREATE TABLE IF NOT EXISTS quant_scores (
        ticker           TEXT,
        universe         TEXT,
        as_of            DATE,
        pct_momentum     DOUBLE,
        pct_valuation    DOUBLE,
        pct_eps_momentum DOUBLE,
        pct_quality      DOUBLE,
        pct_technical    DOUBLE,
        raw_momentum     DOUBLE,
        raw_fwd_pe       DOUBLE,
        raw_pbr          DOUBLE,
        raw_psr          DOUBLE,
        raw_trailing_pe  DOUBLE,
        raw_eps_ttm      DOUBLE,
        raw_fwd_eps      DOUBLE,
        raw_roe          DOUBLE,
        raw_debt_ratio   DOUBLE,
        raw_rsi          DOUBLE,
        above_ma200      BOOLEAN,
        cfo_positive     BOOLEAN,
        company_name     TEXT,
        PRIMARY KEY (ticker, universe, as_of)
    );

    CREATE TABLE IF NOT EXISTS ticker_notes (
        ticker       TEXT PRIMARY KEY,
        opinion      TEXT,
        target_price DOUBLE,
        memo         TEXT,
        tags         TEXT,
        updated_at   TIMESTAMP
    );
```

그리고 migrations 리스트에 추가:

```python
"CREATE INDEX IF NOT EXISTS idx_quant_scores_uni_date ON quant_scores (universe, as_of)",
```

- [ ] **Step 2: repository 함수 4개 추가** — 파일 맨 끝에 추가:

```python
# ── Quant Scores ──────────────────────────────────────────────────────────────

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
                     above_ma200, cfo_positive, company_name)
                VALUES
                    (:ticker, :universe, :as_of,
                     :pct_momentum, :pct_valuation, :pct_eps_momentum, :pct_quality, :pct_technical,
                     :raw_momentum, :raw_fwd_pe, :raw_pbr, :raw_psr, :raw_trailing_pe,
                     :raw_eps_ttm, :raw_fwd_eps, :raw_roe, :raw_debt_ratio, :raw_rsi,
                     :above_ma200, :cfo_positive, :company_name)
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
                    company_name = excluded.company_name
            """), r)
        s.commit()


def get_latest_quant_scores(universe: str) -> list[dict]:
    """(universe, as_of) 인덱스를 타는 최신 배치 조회."""
    with session() as s:
        rows = s.execute(text("""
            SELECT * FROM quant_scores
            WHERE universe = :universe
              AND as_of = (SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe)
            ORDER BY ticker
        """), {"universe": universe}).mappings().all()
        return [dict(r) for r in rows]


def get_quant_ticker(ticker: str, universe: str) -> dict | None:
    with session() as s:
        row = s.execute(text("""
            SELECT * FROM quant_scores
            WHERE ticker = :ticker AND universe = :universe
              AND as_of = (SELECT MAX(as_of) FROM quant_scores WHERE universe = :universe)
        """), {"ticker": ticker, "universe": universe}).mappings().fetchone()
        return dict(row) if row else None


# ── Ticker Notes ──────────────────────────────────────────────────────────────

def upsert_ticker_note(ticker: str, opinion: str | None, target_price: float | None,
                       memo: str | None, tags: str | None) -> None:
    with session() as s:
        s.execute(text("""
            INSERT INTO ticker_notes (ticker, opinion, target_price, memo, tags, updated_at)
            VALUES (:ticker, :opinion, :target_price, :memo, :tags, :now)
            ON CONFLICT (ticker) DO UPDATE SET
                opinion = excluded.opinion, target_price = excluded.target_price,
                memo = excluded.memo, tags = excluded.tags, updated_at = excluded.updated_at
        """), {"ticker": ticker, "opinion": opinion, "target_price": target_price,
               "memo": memo, "tags": tags, "now": datetime.now()})
        s.commit()


def get_ticker_note(ticker: str) -> dict | None:
    with session() as s:
        row = s.execute(
            text("SELECT * FROM ticker_notes WHERE ticker = :ticker"), {"ticker": ticker}
        ).mappings().fetchone()
        return dict(row) if row else None
```

- [ ] **Step 3: 서버 재시작 후 테이블 생성 확인**

```bash
python -c "
from core.repository import get_engine
from sqlalchemy import text
e = get_engine()
with e.connect() as c:
    r = c.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('quant_scores','ticker_notes')\")).fetchall()
    print(r)
"
```
Expected: `[('quant_scores',), ('ticker_notes',)]` (순서 무관)

- [ ] **Step 4: Commit**

```bash
git add core/repository.py
git commit -m "feat: add quant_scores and ticker_notes schema + repo functions"
```

---

## Task 3: Universe Provider — S&P 500 티커 목록

**Files:**
- Create: `core/data/universe_provider.py`

- [ ] **Step 1: 파일 작성**

```python
"""S&P 500 유니버스 티커 목록 제공.

Wikipedia HTML 테이블 파싱으로 티커 취득 (yfinance 제공 없음).
네트워크 불가 시 캐시된 JSON 파일을 fallback으로 사용.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CACHE_PATH = Path("data/sp500_tickers.json")


def get_sp500_tickers() -> list[str]:
    """S&P 500 구성 종목 티커 반환. Wikipedia 파싱 → 캐시 파일 fallback."""
    try:
        tables = pd.read_html(_WIKI_URL)
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(tickers))
        log.info("S&P 500 티커 %d개 취득 (Wikipedia)", len(tickers))
        return tickers
    except Exception as e:
        log.warning("Wikipedia 파싱 실패 (%s) — 캐시 파일 시도", e)
        if _CACHE_PATH.exists():
            tickers = json.loads(_CACHE_PATH.read_text())
            log.info("S&P 500 티커 %d개 취득 (캐시)", len(tickers))
            return tickers
        raise RuntimeError("S&P 500 티커 목록 취득 불가. 네트워크 확인 필요.") from e


UNIVERSE_PROVIDERS = {
    "sp500": get_sp500_tickers,
}


def get_tickers(universe: str) -> list[str]:
    provider = UNIVERSE_PROVIDERS.get(universe)
    if not provider:
        raise ValueError(f"Unknown universe: {universe}. 지원: {list(UNIVERSE_PROVIDERS)}")
    return provider()
```

- [ ] **Step 2: 동작 확인**

```bash
python -c "
from core.data.universe_provider import get_sp500_tickers
t = get_sp500_tickers()
print(len(t), t[:5])
"
```
Expected: `503 ['MMM', 'AOS', 'ABT', ...]` (정확한 숫자/순서는 무관)

- [ ] **Step 3: Commit**

```bash
git add core/data/universe_provider.py
git commit -m "feat: add S&P 500 universe provider"
```

---

## Task 4: Fundamentals Extended — PBR, PSR, ROE, D/E, CFO

**Files:**
- Create: `core/data/fundamentals_extended.py`

- [ ] **Step 1: 파일 작성**

```python
"""확장 펀더멘탈 스냅샷 — PBR, PSR, ROE, D/E Ratio, CFO, EPS TTM 페치.

yfinance Ticker.info 딕셔너리에서 필드 추출.
병렬 페치로 500개 종목 처리 시간 최소화.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtendedSnapshot:
    ticker: str
    as_of: date
    company_name: str | None = None
    # 밸류에이션
    forward_pe: float | None = None
    trailing_pe: float | None = None
    pbr: float | None = None       # priceToBook
    psr: float | None = None       # priceToSalesTrailing12Months
    # 어닝스
    forward_eps: float | None = None
    eps_ttm: float | None = None   # trailingEps
    # 퀄리티
    roe: float | None = None               # returnOnEquity
    debt_to_equity: float | None = None    # debtToEquity (단위: %, 예: 150 = 1.5배)
    operating_cashflow: float | None = None  # operatingCashflow
    error: str | None = field(default=None, hash=False, compare=False)


def _safe(info: dict, key: str) -> float | None:
    v = info.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f  # NaN guard
    except (ValueError, TypeError):
        return None


def _fetch_one(ticker: str, as_of: date) -> ExtendedSnapshot:
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        return ExtendedSnapshot(
            ticker=ticker,
            as_of=as_of,
            company_name=info.get("shortName") or info.get("longName"),
            forward_pe=_safe(info, "forwardPE"),
            trailing_pe=_safe(info, "trailingPE"),
            pbr=_safe(info, "priceToBook"),
            psr=_safe(info, "priceToSalesTrailing12Months"),
            forward_eps=_safe(info, "forwardEps"),
            eps_ttm=_safe(info, "trailingEps"),
            roe=_safe(info, "returnOnEquity"),
            debt_to_equity=_safe(info, "debtToEquity"),
            operating_cashflow=_safe(info, "operatingCashflow"),
        )
    except Exception as e:
        log.warning("ExtendedSnapshot 페치 실패 (%s): %s", ticker, e)
        return ExtendedSnapshot(ticker=ticker, as_of=as_of, error=str(e))


def fetch_extended(tickers: list[str], max_workers: int = 20) -> list[ExtendedSnapshot]:
    """ThreadPool으로 복수 티커 동시 페치."""
    from datetime import date as dt_date
    today = dt_date.today()
    results: list[ExtendedSnapshot] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(tickers))) as ex:
        futures = {ex.submit(_fetch_one, t, today): t for t in tickers}
        for future in as_completed(futures):
            results.append(future.result())
    return results
```

- [ ] **Step 2: Commit**

```bash
git add core/data/fundamentals_extended.py
git commit -m "feat: add extended fundamentals provider (PBR/PSR/ROE/DE/CFO)"
```

---

## Task 5: Factor — Price Momentum (12-1M)

**Files:**
- Create: `core/factors/price_momentum.py`
- Create: `tests/test_price_momentum.py`

- [ ] **Step 1: 테스트 작성**

```python
"""tests/test_price_momentum.py"""
from datetime import date
import pandas as pd
import pytest
from unittest.mock import patch


def test_momentum_formula():
    """12-1M = price(t-1M) / price(t-12M) - 1 검증."""
    from core.factors.price_momentum import _compute_12_1m_momentum

    # price 1년 전 100, 1개월 전 120 → momentum = 120/100 - 1 = 0.20
    result = _compute_12_1m_momentum(price_12m_ago=100.0, price_1m_ago=120.0)
    assert abs(result - 0.20) < 1e-9


def test_momentum_returns_nan_on_zero_base():
    from core.factors.price_momentum import _compute_12_1m_momentum
    import math
    result = _compute_12_1m_momentum(price_12m_ago=0.0, price_1m_ago=120.0)
    assert math.isnan(result)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_price_momentum.py -v
```
Expected: `ERROR` (모듈 없음)

- [ ] **Step 3: 구현 파일 작성**

```python
"""core/factors/price_momentum.py — 12-1M 가격 모멘텀 팩터.

12-1M 정의: price(t-1M) / price(t-12M) - 1
단기 1개월을 제거해 Mean Reversion 노이즈를 차단한다.
(Jegadeesh & Titman, 1993 / Fama-French momentum anomaly)
"""
from __future__ import annotations

import math
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import ClassVar

import pandas as pd
from sqlalchemy import text

import core.repository as repo
from core.factors.base import Factor

log = logging.getLogger(__name__)


def _compute_12_1m_momentum(price_12m_ago: float, price_1m_ago: float) -> float:
    if price_12m_ago == 0:
        return math.nan
    return price_1m_ago / price_12m_ago - 1


class PriceMomentumFactor(Factor):
    name: ClassVar[str] = "price_momentum"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        date_12m = as_of - relativedelta(months=12)
        date_1m = as_of - relativedelta(months=1)
        scores: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                # prices_cache에서 가장 가까운 거래일 종가 조회
                r12 = s.execute(text("""
                    SELECT close FROM prices_cache
                    WHERE ticker = :t AND date <= :d
                    ORDER BY date DESC LIMIT 1
                """), {"t": ticker, "d": date_12m}).fetchone()

                r1 = s.execute(text("""
                    SELECT close FROM prices_cache
                    WHERE ticker = :t AND date <= :d
                    ORDER BY date DESC LIMIT 1
                """), {"t": ticker, "d": date_1m}).fetchone()

                if r12 and r1 and r12[0] and r1[0]:
                    scores[ticker] = _compute_12_1m_momentum(r12[0], r1[0])
                else:
                    scores[ticker] = math.nan

        return pd.Series(scores)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_price_momentum.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add core/factors/price_momentum.py tests/test_price_momentum.py
git commit -m "feat: add 12-1M price momentum factor"
```

---

## Task 6: Factor — Valuation (Winsorizing + Z-score)

**Files:**
- Create: `core/factors/valuation.py`
- Create: `tests/test_valuation.py`

- [ ] **Step 1: 테스트 작성**

```python
"""tests/test_valuation.py"""
import numpy as np
import pandas as pd


def test_winsorize_clips_outliers():
    from core.factors.valuation import _winsorize_series
    s = pd.Series([1.0, 2.0, 3.0, 1000.0])  # 1000은 상위 1% 아웃라이어
    result = _winsorize_series(s, limits=(0.01, 0.01))
    assert result.max() < 1000.0


def test_zscore_combines_pe_pbr():
    from core.factors.valuation import _combined_value_zscore
    pe = pd.Series([10.0, 20.0, 30.0], index=["A", "B", "C"])
    pbr = pd.Series([1.0, 2.0, 3.0], index=["A", "B", "C"])
    result = _combined_value_zscore(pe, pbr)
    # 낮은 PER/PBR인 A가 가장 낮은 z-score여야 함 (역수 처리 전)
    assert result["A"] < result["C"]


def test_fallback_rank_on_near_zero_std():
    from core.factors.valuation import _combined_value_zscore
    # 모든 값이 같으면 std=0 → rank fallback
    pe = pd.Series([10.0, 10.0, 10.0], index=["A", "B", "C"])
    pbr = pd.Series([2.0, 2.0, 2.0], index=["A", "B", "C"])
    result = _combined_value_zscore(pe, pbr)
    assert result is not None  # fallback이 crash하지 않음
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_valuation.py -v
```
Expected: ERROR

- [ ] **Step 3: 구현 파일 작성**

```python
"""core/factors/valuation.py — 통합 밸류에이션 팩터.

Forward PER + PBR을 Winsorizing 후 Z-score 합산.
낮을수록 저평가이므로 백분위 계산 시 역수 처리(1 - pct).

Winsorizing: 극단 아웃라이어(PER 수천배 기업)가 유니버스 Z-score를
            왜곡하는 것을 막기 위해 1%·99% 분위수로 강제 클리핑.
Rank Fallback: std ≈ 0인 엣지 케이스에서 rank 기반 표준화로 전환.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import ClassVar

import numpy as np
import pandas as pd
from scipy.stats.mstats import winsorize

from core.factors.base import Factor
import core.repository as repo

log = logging.getLogger(__name__)


def _winsorize_series(s: pd.Series, limits=(0.01, 0.01)) -> pd.Series:
    """NaN 제외 후 윈저라이징, NaN은 원위치 복원."""
    mask = s.notna()
    result = s.copy()
    result[mask] = winsorize(s[mask].values, limits=limits)
    return result


def _combined_value_zscore(
    fwd_pe: pd.Series,
    pbr: pd.Series,
) -> pd.Series:
    """PER + PBR Winsorize → Z-score → 평균. 낮을수록 저평가."""
    w_pe = _winsorize_series(fwd_pe)
    w_pbr = _winsorize_series(pbr)

    def to_zscore(s: pd.Series) -> pd.Series:
        std = s.std()
        if std < 1e-6:
            # Fallback: rank 기반 표준화 [-1, 1] 범위
            # std ≈ 0은 모든 종목이 동일 값인 엣지 케이스 (적자 전환 후 PE 일괄 결측 등)
            log.warning("Z-score std≈0 — rank fallback 사용")
            r = s.rank(pct=True)
            return r * 2 - 1
        return (s - s.mean()) / std

    combined = (to_zscore(w_pe) + to_zscore(w_pbr)) / 2
    return combined


class ValuationFactor(Factor):
    name: ClassVar[str] = "valuation"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        from sqlalchemy import text

        fwd_pe: dict[str, float] = {}
        pbr: dict[str, float] = {}

        with repo.session() as s:
            for ticker in tickers:
                row = s.execute(text("""
                    SELECT raw_fwd_pe, raw_pbr FROM quant_scores
                    WHERE ticker = :t AND universe = 'sp500'
                    ORDER BY as_of DESC LIMIT 1
                """), {"t": ticker}).fetchone()
                if row:
                    if row[0] is not None and row[0] > 0:
                        fwd_pe[ticker] = row[0]
                    if row[1] is not None and row[1] > 0:
                        pbr[ticker] = row[1]

        pe_s = pd.Series(fwd_pe)
        pbr_s = pd.Series(pbr)
        common = pe_s.index.intersection(pbr_s.index)
        if common.empty:
            return pd.Series({t: float("nan") for t in tickers})

        combined = _combined_value_zscore(pe_s[common], pbr_s[common])
        return combined.reindex(tickers)
```

> **Note:** ValuationFactor.compute는 universe_scorer가 raw 값을 먼저 저장한 후 호출되므로 quant_scores에서 읽는다. universe_scorer Task에서 raw 값을 직접 넘기는 방식으로 호출함.

- [ ] **Step 4: 테스트 통과**

```bash
.venv/bin/pytest tests/test_valuation.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add core/factors/valuation.py tests/test_valuation.py
git commit -m "feat: add valuation factor with winsorizing + rank fallback"
```

---

## Task 7: Factor — EPS Momentum (3M slope 추가)

**Files:**
- Modify: `core/factors/forward_eps_momentum.py`

- [ ] **Step 1: 3M slope 추가**

기존 파일 전체 교체:

```python
"""core/factors/forward_eps_momentum.py — Forward EPS 모멘텀 팩터.

1M + 3M EPS 변화율 가중 평균으로 기관 컨센서스 추세를 포착.
1M: 최신 컨센서스 변화, 3M: 추세 지속성. 두 기간 조합으로 노이즈 감쇠.
"""
from __future__ import annotations

from datetime import date
from typing import ClassVar

import pandas as pd
from dateutil.relativedelta import relativedelta

import core.repository as repo
from core.factors.base import Factor


class ForwardEpsMomentumFactor(Factor):
    name: ClassVar[str] = "forward_eps_momentum"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        date_1m = as_of - relativedelta(months=1)
        date_3m = as_of - relativedelta(months=3)
        scores: dict[str, float] = {}

        for ticker in tickers:
            current = repo.get_latest_fundamental(ticker, as_of)
            prev_1m = repo.get_latest_fundamental(ticker, date_1m)
            prev_3m = repo.get_latest_fundamental(ticker, date_3m)

            cur_eps = current.get("forward_eps") if current else None
            eps_1m = prev_1m.get("forward_eps") if prev_1m else None
            eps_3m = prev_3m.get("forward_eps") if prev_3m else None

            slope_1m = (
                (cur_eps - eps_1m) / abs(eps_1m)
                if cur_eps is not None and eps_1m and eps_1m != 0
                else 0.0
            )
            slope_3m = (
                (cur_eps - eps_3m) / abs(eps_3m)
                if cur_eps is not None and eps_3m and eps_3m != 0
                else 0.0
            )
            scores[ticker] = 0.5 * slope_1m + 0.5 * slope_3m

        return pd.Series(scores)
```

- [ ] **Step 2: 테스트 확인 (기존 테스트 유지)**

```bash
.venv/bin/pytest tests/ -k "eps" -v 2>/dev/null || echo "no eps tests — ok"
```

- [ ] **Step 3: Commit**

```bash
git add core/factors/forward_eps_momentum.py
git commit -m "feat: extend EPS momentum factor with 3M slope"
```

---

## Task 8: Factor — Quality (ROE + D/E + CFO)

**Files:**
- Create: `core/factors/quality.py`

- [ ] **Step 1: 파일 작성**

```python
"""core/factors/quality.py — 퀄리티 & 지급능력 팩터.

ROE + D/E 역수 결합으로 수익성과 재무 안정성을 동시 평가.
ROE 단독 사용 시 레버리지 과용 기업이 과대평가될 수 있어 부채비율 역수를 결합.
CFO 양수 조건은 이익의 질 검증 — 영업현금흐름이 음수면 이익 조작 가능성.
"""
from __future__ import annotations

import math
from datetime import date
from typing import ClassVar

import pandas as pd

from core.factors.base import Factor


class QualityFactor(Factor):
    name: ClassVar[str] = "quality"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        # universe_scorer가 ExtendedSnapshot 데이터를 직접 전달하는 방식으로 사용됨
        # 여기서는 인터페이스 호환성을 위해 빈 Series 반환
        # 실제 계산은 universe_scorer.py의 _compute_quality_scores()에서 수행
        return pd.Series({t: math.nan for t in tickers})

    @staticmethod
    def score(roe: float | None, debt_to_equity: float | None) -> float:
        """단일 종목 퀄리티 점수 계산.

        debt_to_equity: yfinance 기준 % 단위 (예: 150 = 부채/자본 1.5배)
        """
        if roe is None:
            return math.nan
        de_ratio = (debt_to_equity / 100.0) if debt_to_equity is not None else 1.0
        de_ratio = max(de_ratio, 0.01)  # 0 나눗셈 방지
        return 0.6 * roe + 0.4 * (1.0 / de_ratio)
```

- [ ] **Step 2: Commit**

```bash
git add core/factors/quality.py
git commit -m "feat: add quality factor (ROE + D/E inverse)"
```

---

## Task 9: Factor — Technical (RSI 백분위 + 200일 MA)

**Files:**
- Create: `core/factors/technical.py`
- Create: `tests/test_technical.py`

- [ ] **Step 1: 테스트 작성**

```python
"""tests/test_technical.py"""
import pandas as pd


def test_rsi_calculation():
    from core.factors.technical import _compute_rsi
    # 14일 평균 상승 = 1, 하락 = 0 → RS = inf → RSI = 100
    gains = pd.Series([1.0] * 14 + [0.0] * 14)
    rsi = _compute_rsi(gains, period=14)
    assert rsi > 90  # 완전 상승 구간


def test_above_ma200():
    from core.factors.technical import _above_ma200
    prices = pd.Series(list(range(1, 202)))  # 201개, 마지막이 201
    result = _above_ma200(prices)
    assert result is True  # 201 > MA200(평균≈101)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_technical.py -v
```
Expected: ERROR

- [ ] **Step 3: 구현 파일 작성**

```python
"""core/factors/technical.py — 기술적 지표 팩터.

RSI(14): 유니버스 내 백분위 순위로 변환.
  단순 rsi/100 정규화는 RSI 60~70의 강한 상승 종목을 중립 취급하는 문제가 있어,
  유니버스 상대 백분위로 모멘텀 강도를 반영한다.
200일 MA: 기관 장기 추세 기준선. 하회 시 기관 매수세 유입 불리.
"""
from __future__ import annotations

import math
import logging
from datetime import date, timedelta
from typing import ClassVar

import pandas as pd
from sqlalchemy import text

import core.repository as repo
from core.factors.base import Factor

log = logging.getLogger(__name__)


def _compute_rsi(price_series: pd.Series, period: int = 14) -> float:
    """단일 종목 RSI 계산. price_series는 종가 시계열."""
    if len(price_series) < period + 1:
        return math.nan
    delta = price_series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if not math.isnan(val) else math.nan


def _above_ma200(price_series: pd.Series) -> bool:
    """현재 종가가 200일 단순이동평균 위인지 여부."""
    if len(price_series) < 200:
        return False
    ma200 = price_series.iloc[-200:].mean()
    return float(price_series.iloc[-1]) > ma200


class TechnicalFactor(Factor):
    name: ClassVar[str] = "technical"

    def compute(self, tickers: list[str], as_of: date) -> pd.Series:
        # universe_scorer에서 직접 계산하므로 stub
        return pd.Series({t: math.nan for t in tickers})

    @staticmethod
    def compute_raw(ticker: str, as_of: date) -> dict:
        """단일 종목 RSI + MA200 계산. 결과: {rsi, above_ma200}"""
        start = as_of - timedelta(days=300)
        with repo.session() as s:
            rows = s.execute(text("""
                SELECT date, close FROM prices_cache
                WHERE ticker = :t AND date >= :start AND date <= :as_of
                ORDER BY date ASC
            """), {"t": ticker, "start": start, "as_of": as_of}).fetchall()

        if not rows:
            return {"rsi": math.nan, "above_ma200": False}

        prices = pd.Series([r[1] for r in rows], dtype=float)
        return {
            "rsi": _compute_rsi(prices, period=14),
            "above_ma200": _above_ma200(prices),
        }
```

- [ ] **Step 4: 테스트 통과**

```bash
.venv/bin/pytest tests/test_technical.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add core/factors/technical.py tests/test_technical.py
git commit -m "feat: add technical factor (RSI percentile + 200MA)"
```

---

## Task 10: Universe Scorer — 배치 계산 오케스트레이터

**Files:**
- Create: `core/scoring/__init__.py`
- Create: `core/scoring/universe_scorer.py`

- [ ] **Step 1: `__init__.py` 생성**

```python
# core/scoring/__init__.py
```

- [ ] **Step 2: `universe_scorer.py` 작성**

```python
"""core/scoring/universe_scorer.py — 유니버스 배치 스코어링 오케스트레이터.

실행 흐름:
1. 유니버스 티커 목록 취득
2. OHLCV 캐시 갱신 (price_momentum, technical 계산용)
3. 확장 펀더멘탈 페치 (valuation, quality, eps 계산용)
4. 5팩터 raw 값 계산
5. 각 팩터를 유니버스 내 백분위(0~1)로 변환
6. DuckDB quant_scores upsert
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from core.data.universe_provider import get_tickers
from core.data.fundamentals_extended import fetch_extended, ExtendedSnapshot
from core.data.ohlcv_cache import fetch_ohlcv
from core.factors.price_momentum import PriceMomentumFactor
from core.factors.forward_eps_momentum import ForwardEpsMomentumFactor
from core.factors.quality import QualityFactor
from core.factors.technical import TechnicalFactor
import core.repository as repo

log = logging.getLogger(__name__)


def _percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """유니버스 내 백분위 순위(0~1). ascending=False이면 낮을수록 높은 점수."""
    clean = series.dropna()
    if clean.empty:
        return pd.Series(dtype=float)
    ranked = clean.rank(pct=True, ascending=ascending)
    return ranked.reindex(series.index)


def run_batch(universe: str = "sp500") -> dict:
    """전체 유니버스 배치 스코어링 실행. 완료 후 통계 dict 반환."""
    today = date.today()
    log.info("[Universe Scorer] 시작: %s %s", universe, today)

    # 1. 유니버스 티커 목록
    tickers = get_tickers(universe)
    log.info("[Universe Scorer] 티커 %d개", len(tickers))

    # 2. OHLCV 캐시 갱신 (1년치 — momentum 12M 계산 필요)
    start_ohlcv = today - timedelta(days=380)
    log.info("[Universe Scorer] OHLCV 갱신 중...")
    _, warns = fetch_ohlcv(tickers, start_ohlcv, today)
    if warns:
        log.warning("OHLCV 경고 %d건: %s...", len(warns), warns[:3])

    # 3. 확장 펀더멘탈 페치
    log.info("[Universe Scorer] 펀더멘탈 페치 중...")
    snaps: list[ExtendedSnapshot] = fetch_extended(tickers, max_workers=20)
    snap_map: dict[str, ExtendedSnapshot] = {s.ticker: s for s in snaps}

    # 4. 팩터별 raw 값 계산
    log.info("[Universe Scorer] 팩터 계산 중...")

    # 4a. Price Momentum
    momentum_factor = PriceMomentumFactor()
    raw_momentum: pd.Series = momentum_factor.compute(tickers, today)

    # 4b. EPS Momentum
    eps_factor = ForwardEpsMomentumFactor()
    raw_eps: pd.Series = eps_factor.compute(tickers, today)

    # 4c. Valuation raw (PER, PBR — Winsorize + Z-score는 percentile 전에 처리)
    raw_fwd_pe = pd.Series({t: snap_map[t].forward_pe for t in tickers if t in snap_map})
    raw_pbr    = pd.Series({t: snap_map[t].pbr       for t in tickers if t in snap_map})

    from core.factors.valuation import _winsorize_series, _combined_value_zscore
    w_pe  = _winsorize_series(raw_fwd_pe.dropna())
    w_pbr = _winsorize_series(raw_pbr.dropna())
    common = w_pe.index.intersection(w_pbr.index)
    if common.empty:
        raw_valuation = pd.Series({t: math.nan for t in tickers})
    else:
        raw_valuation = _combined_value_zscore(w_pe[common], w_pbr[common]).reindex(tickers)

    # 4d. Quality
    raw_quality_vals: dict[str, float] = {}
    for ticker in tickers:
        snap = snap_map.get(ticker)
        if snap:
            raw_quality_vals[ticker] = QualityFactor.score(snap.roe, snap.debt_to_equity)
        else:
            raw_quality_vals[ticker] = math.nan
    raw_quality = pd.Series(raw_quality_vals)

    # 4e. Technical (RSI + MA200) — ThreadPool으로 병렬 계산
    log.info("[Universe Scorer] 기술적 지표 계산 중 (병렬)...")
    tech_raw: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(TechnicalFactor.compute_raw, t, today): t for t in tickers}
        for future in as_completed(futures):
            t = futures[future]
            try:
                tech_raw[t] = future.result()
            except Exception as e:
                log.warning("기술 지표 실패 (%s): %s", t, e)
                tech_raw[t] = {"rsi": math.nan, "above_ma200": False}

    raw_rsi = pd.Series({t: tech_raw[t]["rsi"] for t in tickers})
    above_ma200 = {t: tech_raw[t]["above_ma200"] for t in tickers}

    # 4f. Technical composite: RSI 백분위 + MA200
    rsi_pct = _percentile_rank(raw_rsi, ascending=True)
    ma200_s = pd.Series({t: 1.0 if above_ma200[t] else 0.0 for t in tickers})
    raw_technical = (0.6 * ma200_s + 0.4 * rsi_pct.reindex(tickers, fill_value=0.5))

    # 5. 백분위 변환
    pct_momentum     = _percentile_rank(raw_momentum,  ascending=True)
    pct_valuation    = _percentile_rank(raw_valuation, ascending=False)  # 낮을수록 좋음
    pct_eps          = _percentile_rank(raw_eps,       ascending=True)
    pct_quality      = _percentile_rank(raw_quality,   ascending=True)
    pct_technical    = _percentile_rank(raw_technical, ascending=True)

    # 6. DB upsert
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
            "above_ma200":      above_ma200.get(ticker, False),
            "cfo_positive":     bool(snap.operating_cashflow and snap.operating_cashflow > 0) if snap else False,
            "company_name":     snap.company_name if snap else None,
        })

    repo.upsert_quant_scores(rows)
    log.info("[Universe Scorer] 완료: %d행 upsert", len(rows))
    return {"universe": universe, "as_of": str(today), "count": len(rows)}


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 3: 수동 실행 테스트 (처음 실행은 OHLCV 다운로드로 수 분 소요)**

```bash
python -c "
from core.scoring.universe_scorer import run_batch
result = run_batch('sp500')
print(result)
"
```
Expected: `{'universe': 'sp500', 'as_of': '2026-05-28', 'count': 503}`

- [ ] **Step 4: Commit**

```bash
git add core/scoring/__init__.py core/scoring/universe_scorer.py
git commit -m "feat: add universe scorer batch pipeline"
```

---

## Task 11: API 모델 추가

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: QuantScoreOut, TickerNoteIn, TickerNoteOut 추가** — 파일 끝에 추가:

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


class TickerNoteIn(BaseModel):
    opinion: str | None = None
    target_price: float | None = None
    memo: str | None = None
    tags: str | None = None


class TickerNoteOut(TickerNoteIn):
    ticker: str
    updated_at: datetime | None = None
```

- [ ] **Step 2: Commit**

```bash
git add api/models.py
git commit -m "feat: add QuantScoreOut and TickerNote models"
```

---

## Task 12: API Router — screener.py

**Files:**
- Create: `api/routers/screener.py`
- Modify: `api/main.py`

- [ ] **Step 1: screener.py 작성**

```python
"""api/routers/screener.py — 퀀트 스크리너 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from api.auth import require_auth
from api.models import QuantScoreOut, TickerNoteIn, TickerNoteOut
import core.repository as repo

router = APIRouter(
    prefix="/api/screener",
    tags=["screener"],
    dependencies=[Depends(require_auth)],
)


@router.get("/scores", response_model=list[QuantScoreOut])
def get_scores(universe: str = "sp500"):
    """유니버스 전체 최신 퀀트 스코어 반환. 프론트엔드 최초 로드 시 1회 호출."""
    rows = repo.get_latest_quant_scores(universe)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"유니버스 '{universe}' 데이터 없음. /api/screener/refresh 먼저 실행 필요."
        )
    return rows


@router.get("/ticker/{ticker}", response_model=QuantScoreOut)
def get_ticker(ticker: str, universe: str = "sp500"):
    """단일 종목 상세 퀀트 스코어 반환."""
    row = repo.get_quant_ticker(ticker.upper(), universe)
    if not row:
        raise HTTPException(status_code=404, detail=f"{ticker} 데이터 없음")
    return row


@router.post("/refresh")
def refresh(universe: str = "sp500", background_tasks: BackgroundTasks = None):
    """배치 스코어링 트리거. 백그라운드로 실행."""
    from core.scoring.universe_scorer import run_batch

    def _run():
        try:
            run_batch(universe)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("배치 실패: %s", e)

    if background_tasks:
        background_tasks.add_task(_run)
        return {"status": "started", "universe": universe}
    else:
        result = run_batch(universe)
        return result


@router.get("/notes/{ticker}", response_model=TickerNoteOut | None)
def get_note(ticker: str):
    return repo.get_ticker_note(ticker.upper())


@router.put("/notes/{ticker}", response_model=TickerNoteOut)
def upsert_note(ticker: str, body: TickerNoteIn):
    t = ticker.upper()
    repo.upsert_ticker_note(
        ticker=t,
        opinion=body.opinion,
        target_price=body.target_price,
        memo=body.memo,
        tags=body.tags,
    )
    row = repo.get_ticker_note(t)
    return row
```

- [ ] **Step 2: main.py에 라우터 등록**

```python
# api/main.py 기존 import 아래에 추가:
from api.routers.screener import router as screener_router

# app.include_router(backtest_router) 아래에 추가:
app.include_router(screener_router)
```

- [ ] **Step 3: 서버 재시작 후 엔드포인트 확인**

```bash
curl -s http://localhost:8000/api/screener/scores?universe=sp500 | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(type(d), len(d) if isinstance(d, list) else d)
"
```
Expected: `<class 'list'> 503` (배치 실행 후) 또는 `404` (배치 전)

- [ ] **Step 4: Commit**

```bash
git add api/routers/screener.py api/main.py
git commit -m "feat: add screener API router (scores, ticker, refresh, notes)"
```

---

## Task 13: 프론트엔드 타입 + API 함수

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: types.ts에 추가** (파일 끝에 append):

```typescript
export interface QuantScore {
  ticker: string;
  universe: string;
  as_of: string;
  company_name: string | null;
  pct_momentum: number | null;
  pct_valuation: number | null;
  pct_eps_momentum: number | null;
  pct_quality: number | null;
  pct_technical: number | null;
  raw_momentum: number | null;
  raw_fwd_pe: number | null;
  raw_pbr: number | null;
  raw_psr: number | null;
  raw_trailing_pe: number | null;
  raw_eps_ttm: number | null;
  raw_fwd_eps: number | null;
  raw_roe: number | null;
  raw_debt_ratio: number | null;
  raw_rsi: number | null;
  above_ma200: boolean | null;
  cfo_positive: boolean | null;
}

export interface FactorWeights {
  momentum: number;
  valuation: number;
  eps_momentum: number;
  quality: number;
  technical: number;
}

export interface TickerNote {
  ticker: string;
  opinion: string | null;
  target_price: number | null;
  memo: string | null;
  tags: string | null;
  updated_at: string | null;
}
```

- [ ] **Step 2: api.ts에 추가** (파일 끝에 append):

```typescript
export const screenerApi = {
  scores: (universe = "sp500") =>
    request<QuantScore[]>(`/api/screener/scores?universe=${universe}`),
  ticker: (ticker: string, universe = "sp500") =>
    request<QuantScore>(`/api/screener/ticker/${ticker}?universe=${universe}`),
  refresh: (universe = "sp500") =>
    request<{ status: string }>(`/api/screener/refresh?universe=${universe}`, { method: "POST" }),
  getNote: (ticker: string) =>
    request<TickerNote | null>(`/api/screener/notes/${ticker}`),
  upsertNote: (ticker: string, body: Omit<TickerNote, "ticker" | "updated_at">) =>
    request<TickerNote>(`/api/screener/notes/${ticker}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat: add QuantScore types and screener API client"
```

---

## Task 14: Nav 업데이트

**Files:**
- Modify: `frontend/components/nav.tsx`

- [ ] **Step 1: 종목분석 링크 추가**

`links` 배열에 항목 추가:

```typescript
const links = [
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/holdings", label: "보유종목" },
  { href: "/backtest", label: "백테스트" },
  { href: "/screener", label: "종목분석" },   // 추가
];
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/nav.tsx
git commit -m "feat: add 종목분석 nav link"
```

---

## Task 15: 컴포넌트 — FactorSidebar

**Files:**
- Create: `frontend/components/screener/factor-sidebar.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/components/screener/factor-sidebar.tsx
"use client";

import type { FactorWeights } from "@/lib/types";

interface Props {
  universe: string;
  onUniverseChange: (u: string) => void;
  weights: FactorWeights;
  onWeightsChange: (w: FactorWeights) => void;
  hardFilters: { ma200: boolean; cfo: boolean };
  onHardFiltersChange: (f: { ma200: boolean; cfo: boolean }) => void;
  totalCount: number;
  filteredCount: number;
}

const FACTOR_LABELS: { key: keyof FactorWeights; label: string }[] = [
  { key: "momentum",     label: "가격 모멘텀" },
  { key: "valuation",    label: "밸류에이션" },
  { key: "eps_momentum", label: "EPS 모멘텀" },
  { key: "quality",      label: "퀄리티" },
  { key: "technical",    label: "기술적 지표" },
];

function normalizeWeights(w: FactorWeights): FactorWeights {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (total === 0) return { momentum: 20, valuation: 20, eps_momentum: 20, quality: 20, technical: 20 };
  return Object.fromEntries(
    Object.entries(w).map(([k, v]) => [k, Math.round((v / total) * 100)])
  ) as FactorWeights;
}

export function FactorSidebar({
  universe, onUniverseChange,
  weights, onWeightsChange,
  hardFilters, onHardFiltersChange,
  totalCount, filteredCount,
}: Props) {
  const norm = normalizeWeights(weights);
  const total = Object.values(norm).reduce((a, b) => a + b, 0);

  const handleSlider = (key: keyof FactorWeights, val: number) => {
    onWeightsChange({ ...weights, [key]: val });
  };

  return (
    <aside className="sticky top-20 w-56 shrink-0 flex flex-col gap-4">
      {/* 유니버스 선택 */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">유니버스</p>
        <select
          value={universe}
          onChange={(e) => onUniverseChange(e.target.value)}
          className="w-full rounded border border-border bg-muted px-2 py-1 text-sm"
        >
          <option value="sp500">S&P 500</option>
        </select>
      </div>

      {/* 팩터 가중치 */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">팩터 가중치</p>
          <span className={`text-xs font-bold ${total === 100 ? "text-green-600" : "text-amber-500"}`}>
            합계 {total}%
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {FACTOR_LABELS.map(({ key, label }) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="text-foreground">{label}</span>
                <span className="font-bold text-blue-600">{norm[key]}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={weights[key]}
                onChange={(e) => handleSlider(key, Number(e.target.value))}
                className="w-full accent-blue-500"
              />
            </div>
          ))}
        </div>
      </div>

      {/* 하드 필터 */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">하드 필터</p>
        <label className="flex items-center gap-2 text-sm cursor-pointer mb-1">
          <input
            type="checkbox"
            checked={hardFilters.ma200}
            onChange={(e) => onHardFiltersChange({ ...hardFilters, ma200: e.target.checked })}
          />
          200일 MA 하회 제외
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={hardFilters.cfo}
            onChange={(e) => onHardFiltersChange({ ...hardFilters, cfo: e.target.checked })}
          />
          CFO 음수 제외
        </label>
      </div>

      {/* 결과 요약 */}
      <p className="text-xs text-muted-foreground">
        {filteredCount} / {totalCount}개 종목
      </p>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/screener/factor-sidebar.tsx
git commit -m "feat: add FactorSidebar component"
```

---

## Task 16: 컴포넌트 — RankingTable

**Files:**
- Create: `frontend/components/screener/ranking-table.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/components/screener/ranking-table.tsx
"use client";

import { useRouter } from "next/navigation";
import type { QuantScore, FactorWeights } from "@/lib/types";

interface Props {
  scores: QuantScore[];
  weights: FactorWeights;
  hardFilters: { ma200: boolean; cfo: boolean };
  topN?: number;
}

function normalizeWeights(w: FactorWeights): FactorWeights {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (total === 0) return { momentum: 0.2, valuation: 0.2, eps_momentum: 0.2, quality: 0.2, technical: 0.2 };
  return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v / total])) as FactorWeights;
}

function compositeScore(s: QuantScore, w: FactorWeights): number {
  const pairs: [number | null, number][] = [
    [s.pct_momentum,     w.momentum],
    [s.pct_valuation,    w.valuation],
    [s.pct_eps_momentum, w.eps_momentum],
    [s.pct_quality,      w.quality],
    [s.pct_technical,    w.technical],
  ];
  let sum = 0, totalW = 0;
  for (const [val, wt] of pairs) {
    if (val !== null && wt > 0) { sum += val * wt; totalW += wt; }
  }
  return totalW > 0 ? sum / totalW : 0;
}

function pctCell(val: number | null) {
  if (val === null) return <td className="px-2 py-1.5 text-right text-muted-foreground text-xs">—</td>;
  const color = val >= 0.7 ? "text-green-600" : val <= 0.3 ? "text-red-500" : "text-amber-500";
  return <td className={`px-2 py-1.5 text-right text-xs font-medium ${color}`}>{val.toFixed(2)}</td>;
}

export function RankingTable({ scores, weights, hardFilters, topN = 50 }: Props) {
  const router = useRouter();
  const norm = normalizeWeights(weights);

  const filtered = scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (hardFilters.cfo  && s.cfo_positive === false) return false;
    return true;
  });

  const ranked = filtered
    .map((s) => ({ ...s, composite: compositeScore(s, norm) }))
    .sort((a, b) => b.composite - a.composite)
    .slice(0, topN);

  if (ranked.length === 0) {
    return <p className="text-muted-foreground text-sm py-8 text-center">데이터 없음. /api/screener/refresh 실행 필요.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/50">
            <th className="px-2 py-2 text-left text-xs text-muted-foreground w-8">#</th>
            <th className="px-2 py-2 text-left text-xs text-muted-foreground">티커</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">종합</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">모멘텀</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">밸류</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">EPS</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">퀄리티</th>
            <th className="px-2 py-2 text-right text-xs text-muted-foreground">기술적</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((s, i) => (
            <tr
              key={s.ticker}
              className="border-b border-border hover:bg-muted/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/screener/${s.ticker}`)}
            >
              <td className="px-2 py-1.5 text-xs text-muted-foreground">{i + 1}</td>
              <td className="px-2 py-1.5 font-bold text-blue-700">{s.ticker}</td>
              <td className="px-2 py-1.5 text-right">
                <span className="bg-blue-100 text-blue-800 rounded px-1.5 py-0.5 text-xs font-bold">
                  {s.composite.toFixed(2)}
                </span>
              </td>
              {pctCell(s.pct_momentum)}
              {pctCell(s.pct_valuation)}
              {pctCell(s.pct_eps_momentum)}
              {pctCell(s.pct_quality)}
              {pctCell(s.pct_technical)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/screener/ranking-table.tsx
git commit -m "feat: add RankingTable with client-side weighting"
```

---

## Task 17: 컴포넌트 — RadarChart + FactorBars

**Files:**
- Create: `frontend/components/screener/radar-chart.tsx`
- Create: `frontend/components/screener/factor-bars.tsx`

- [ ] **Step 1: radar-chart.tsx 작성**

```typescript
// frontend/components/screener/radar-chart.tsx
interface RadarPoint { label: string; value: number }

interface Props { points: RadarPoint[] }

export function RadarChart({ points }: Props) {
  const n = points.length;
  const cx = 100, cy = 100, r = 75;
  const angleStep = (2 * Math.PI) / n;

  const toXY = (i: number, radius: number) => ({
    x: cx + radius * Math.sin(i * angleStep - Math.PI / 2),  // -π/2 로 위쪽이 첫 꼭짓점
    y: cy - radius * Math.cos(i * angleStep - Math.PI / 2),
  });

  const bgPolygons = [0.25, 0.5, 0.75, 1.0].map((scale) =>
    points.map((_, i) => toXY(i, r * scale)).map((p) => `${p.x},${p.y}`).join(" ")
  );

  const dataPolygon = points
    .map((p, i) => toXY(i, r * Math.max(0, Math.min(1, p.value ?? 0))))
    .map((p) => `${p.x},${p.y}`)
    .join(" ");

  return (
    <svg viewBox="0 0 200 200" className="w-full h-full">
      {/* 배경 격자 */}
      {bgPolygons.map((pts, i) => (
        <polygon key={i} points={pts} fill="none" stroke="#e2e8f0" strokeWidth="0.8" />
      ))}
      {/* 축선 */}
      {points.map((_, i) => {
        const p = toXY(i, r);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="#e2e8f0" strokeWidth="0.8" />;
      })}
      {/* 데이터 영역 */}
      <polygon points={dataPolygon} fill="rgba(59,130,246,0.18)" stroke="#3b82f6" strokeWidth="1.5" />
      {/* 레이블 */}
      {points.map((p, i) => {
        const { x, y } = toXY(i, r + 16);
        return (
          <text
            key={i}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="9"
            fill="#475569"
            fontFamily="sans-serif"
          >
            {p.label}
          </text>
        );
      })}
    </svg>
  );
}
```

- [ ] **Step 2: factor-bars.tsx 작성**

```typescript
// frontend/components/screener/factor-bars.tsx
interface FactorBar { label: string; sublabel: string; value: number | null }

export function FactorBars({ bars }: { bars: FactorBar[] }) {
  return (
    <div className="flex flex-col gap-2">
      {bars.map(({ label, sublabel, value }) => {
        const v = value ?? 0;
        const color = v >= 0.7 ? "bg-green-500" : v <= 0.3 ? "bg-red-400" : "bg-amber-400";
        const textColor = v >= 0.7 ? "text-green-600" : v <= 0.3 ? "text-red-500" : "text-amber-500";
        return (
          <div key={label}>
            <div className="flex justify-between text-xs mb-0.5">
              <span className="text-foreground">
                {label} <span className="text-muted-foreground">{sublabel}</span>
              </span>
              <span className={`font-bold ${textColor}`}>
                {value !== null ? value.toFixed(2) : "—"}
              </span>
            </div>
            <div className="bg-muted rounded h-1.5">
              <div className={`${color} h-full rounded`} style={{ width: `${v * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/screener/radar-chart.tsx frontend/components/screener/factor-bars.tsx
git commit -m "feat: add RadarChart and FactorBars components"
```

---

## Task 18: 컴포넌트 — MetricGrid

**Files:**
- Create: `frontend/components/screener/metric-grid.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/components/screener/metric-grid.tsx
import type { QuantScore } from "@/lib/types";

// RSI 컬러링: 40–70 = 초록(건전 추세), 30–40 = 노랑(경계), ≥70 또는 ≤30 = 빨강(과열/과매도)
function rsiColor(rsi: number | null): string {
  if (rsi === null) return "text-muted-foreground";
  if (rsi >= 40 && rsi < 70) return "text-green-600";
  if (rsi >= 30 && rsi < 40) return "text-amber-500";
  return "text-red-500";
}

function metricColor(val: number | null, goodBelow: boolean, goodThreshold: number, warnThreshold: number): string {
  if (val === null) return "text-muted-foreground";
  if (goodBelow) {
    if (val < goodThreshold) return "text-green-600";
    if (val > warnThreshold) return "text-red-500";
    return "text-amber-500";
  } else {
    if (val > goodThreshold) return "text-green-600";
    if (val < warnThreshold) return "text-red-500";
    return "text-amber-500";
  }
}

function fmt(val: number | null, decimals = 1, suffix = "x"): string {
  if (val === null) return "—";
  return `${val.toFixed(decimals)}${suffix}`;
}

function fmtPct(val: number | null): string {
  if (val === null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

interface Metric {
  label: string;
  value: string;
  sub: string;
  colorClass: string;
}

export function MetricGrid({ score }: { score: QuantScore }) {
  const metrics: Metric[] = [
    {
      label: "Trailing PER",
      value: fmt(score.raw_trailing_pe),
      sub: "S&P500 avg ~21x",
      colorClass: metricColor(score.raw_trailing_pe, true, 21, 40),
    },
    {
      label: "Forward PER",
      value: fmt(score.raw_fwd_pe),
      sub: "S&P500 avg ~18x",
      colorClass: metricColor(score.raw_fwd_pe, true, 18, 35),
    },
    {
      label: "PBR",
      value: fmt(score.raw_pbr),
      sub: "S&P500 avg ~4x",
      colorClass: metricColor(score.raw_pbr, true, 4, 10),
    },
    {
      label: "PSR",
      value: fmt(score.raw_psr),
      sub: "S&P500 avg ~2.8x",
      colorClass: metricColor(score.raw_psr, true, 3, 10),
    },
    {
      label: "EPS (TTM)",
      value: score.raw_eps_ttm !== null ? `$${score.raw_eps_ttm.toFixed(2)}` : "—",
      sub: "Trailing 12M",
      colorClass: score.raw_eps_ttm !== null && score.raw_eps_ttm > 0 ? "text-green-600" : "text-red-500",
    },
    {
      label: "Fwd EPS",
      value: score.raw_fwd_eps !== null ? `$${score.raw_fwd_eps.toFixed(2)}` : "—",
      sub: score.raw_eps_ttm && score.raw_fwd_eps
        ? `vs TTM ${score.raw_fwd_eps > score.raw_eps_ttm ? "+" : ""}${(((score.raw_fwd_eps - score.raw_eps_ttm) / Math.abs(score.raw_eps_ttm)) * 100).toFixed(0)}%`
        : "Forward 12M",
      colorClass: score.raw_fwd_eps !== null && score.raw_fwd_eps > (score.raw_eps_ttm ?? 0) ? "text-green-600" : "text-amber-500",
    },
    {
      label: "ROE",
      value: fmtPct(score.raw_roe),
      sub: "Return on Equity",
      colorClass: metricColor(score.raw_roe, false, 0.15, 0.05),
    },
    {
      label: "D/E Ratio",
      value: score.raw_debt_ratio !== null ? score.raw_debt_ratio.toFixed(2) : "—",
      sub: "Debt / Equity",
      colorClass: metricColor(score.raw_debt_ratio, true, 0.5, 2.0),
    },
    {
      label: "RSI (14)",
      value: score.raw_rsi !== null ? score.raw_rsi.toFixed(1) : "—",
      sub: score.raw_rsi !== null
        ? score.raw_rsi >= 70 ? "과열 구간" : score.raw_rsi <= 30 ? "과매도" : score.raw_rsi >= 40 ? "건전 추세" : "약세 경계"
        : "",
      colorClass: rsiColor(score.raw_rsi),
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-2">
      {metrics.map(({ label, value, sub, colorClass }) => (
        <div key={label} className="rounded-lg bg-muted/40 px-3 py-2 border border-border">
          <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
          <p className={`text-base font-bold ${colorClass}`}>{value}</p>
          <p className="text-xs text-muted-foreground">{sub}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/screener/metric-grid.tsx
git commit -m "feat: add MetricGrid with dynamic coloring (RSI 40-70 green)"
```

---

## Task 19: 컴포넌트 — NoteForm

**Files:**
- Create: `frontend/components/screener/note-form.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/components/screener/note-form.tsx
"use client";

import { useState } from "react";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import type { TickerNote } from "@/lib/types";

export function NoteForm({ ticker }: { ticker: string }) {
  const { data: saved, mutate } = useSWR(
    `/api/screener/notes/${ticker}`,
    () => screenerApi.getNote(ticker)
  );

  const [opinion, setOpinion]         = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [memo, setMemo]               = useState("");
  const [tags, setTags]               = useState("");
  const [saving, setSaving]           = useState(false);

  // saved 로드 시 초기화
  useState(() => {
    if (saved) {
      setOpinion(saved.opinion ?? "");
      setTargetPrice(saved.target_price?.toString() ?? "");
      setMemo(saved.memo ?? "");
      setTags(saved.tags ?? "");
    }
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      await screenerApi.upsertNote(ticker, {
        opinion: opinion || null,
        target_price: targetPrice ? parseFloat(targetPrice) : null,
        memo: memo || null,
        tags: tags || null,
      });
      mutate();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">투자 의견 기록</p>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">투자 의견</label>
        <select
          value={opinion}
          onChange={(e) => setOpinion(e.target.value)}
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        >
          <option value="">선택</option>
          <option value="매수검토">매수 검토</option>
          <option value="보유">보유</option>
          <option value="관망">관망</option>
          <option value="매도검토">매도 검토</option>
        </select>
      </div>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">목표가 (USD)</label>
        <input
          type="number"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          placeholder="예: 180.00"
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        />
      </div>

      <div className="flex-1">
        <label className="text-xs text-muted-foreground mb-1 block">메모</label>
        <textarea
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          placeholder="투자 근거, 주요 리스크..."
          className="w-full h-full min-h-[120px] rounded border border-border bg-muted px-2 py-1.5 text-sm resize-none"
        />
      </div>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">태그</label>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="AI, 반도체, 성장주..."
          className="w-full rounded border border-border bg-muted px-2 py-1.5 text-sm"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {saving ? "저장 중..." : "저장"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/screener/note-form.tsx
git commit -m "feat: add NoteForm component with SWR save"
```

---

## Task 20: 스크리닝 페이지

**Files:**
- Create: `frontend/app/screener/page.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/app/screener/page.tsx
"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import type { FactorWeights } from "@/lib/types";
import { FactorSidebar } from "@/components/screener/factor-sidebar";
import { RankingTable } from "@/components/screener/ranking-table";

const DEFAULT_WEIGHTS: FactorWeights = {
  momentum: 25,
  valuation: 20,
  eps_momentum: 20,
  quality: 20,
  technical: 15,
};

export default function ScreenerPage() {
  const [universe, setUniverse] = useState("sp500");
  const [weights, setWeights]   = useState<FactorWeights>(DEFAULT_WEIGHTS);
  const [hardFilters, setHardFilters] = useState({ ma200: true, cfo: true });
  const [refreshing, setRefreshing]   = useState(false);

  const { data: scores = [], isLoading, error } = useSWR(
    `/api/screener/scores?universe=${universe}`,
    () => screenerApi.scores(universe)
  );

  const filteredCount = useMemo(() => scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (hardFilters.cfo  && s.cfo_positive === false) return false;
    return true;
  }).length, [scores, hardFilters]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await screenerApi.refresh(universe); }
    finally { setRefreshing(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-bold tracking-tight">종목분석 — 퀀트 스크리닝</h1>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50"
        >
          {refreshing ? "배치 실행 중..." : "데이터 갱신"}
        </button>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">로딩 중...</p>}
      {error && (
        <p className="text-sm text-amber-600">
          데이터 없음 — &quot;데이터 갱신&quot; 버튼으로 배치 실행 후 새로고침 하세요.
        </p>
      )}

      <div className="flex gap-6 items-start">
        <FactorSidebar
          universe={universe}
          onUniverseChange={setUniverse}
          weights={weights}
          onWeightsChange={setWeights}
          hardFilters={hardFilters}
          onHardFiltersChange={setHardFilters}
          totalCount={scores.length}
          filteredCount={filteredCount}
        />

        <div className="flex-1 min-w-0">
          {scores.length > 0 && (
            <p className="text-xs text-muted-foreground mb-2">
              {scores[0]?.as_of} 기준 · 상위 50개 표시
            </p>
          )}
          <RankingTable
            scores={scores}
            weights={weights}
            hardFilters={hardFilters}
            topN={50}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/screener/page.tsx
git commit -m "feat: add screener page with real-time weight reranking"
```

---

## Task 21: 종목 상세 페이지

**Files:**
- Create: `frontend/app/screener/[ticker]/page.tsx`

- [ ] **Step 1: 파일 작성**

```typescript
// frontend/app/screener/[ticker]/page.tsx
"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import { RadarChart } from "@/components/screener/radar-chart";
import { FactorBars } from "@/components/screener/factor-bars";
import { MetricGrid } from "@/components/screener/metric-grid";
import { NoteForm } from "@/components/screener/note-form";

export default function TickerDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: score, isLoading } = useSWR(
    ticker ? `/api/screener/ticker/${ticker}` : null,
    () => screenerApi.ticker(ticker)
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) router.push(`/screener/${search.trim().toUpperCase()}`);
  };

  const radarPoints = score
    ? [
        { label: "모멘텀",   value: score.pct_momentum     ?? 0 },
        { label: "밸류",     value: score.pct_valuation    ?? 0 },
        { label: "EPS",      value: score.pct_eps_momentum ?? 0 },
        { label: "퀄리티",   value: score.pct_quality      ?? 0 },
        { label: "기술적",   value: score.pct_technical    ?? 0 },
      ]
    : [];

  const factorBars = score
    ? [
        { label: "가격 모멘텀", sublabel: "12-1M",       value: score.pct_momentum     },
        { label: "밸류에이션",  sublabel: "FWD PER+PBR", value: score.pct_valuation    },
        { label: "EPS 모멘텀",  sublabel: "1M+3M 추세",  value: score.pct_eps_momentum },
        { label: "퀄리티",      sublabel: "ROE+D/E",     value: score.pct_quality      },
        { label: "기술적 지표", sublabel: "RSI+200MA",   value: score.pct_technical    },
      ]
    : [];

  const composite = score
    ? [
        score.pct_momentum, score.pct_valuation,
        score.pct_eps_momentum, score.pct_quality, score.pct_technical,
      ].filter((v) => v !== null).reduce((a, b) => a + b!, 0) /
      [score.pct_momentum, score.pct_valuation, score.pct_eps_momentum, score.pct_quality, score.pct_technical].filter((v) => v !== null).length
    : null;

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <form onSubmit={handleSearch} className="flex items-center gap-3 bg-muted/30 rounded-lg px-4 py-3 border border-border">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="티커 검색 (예: AAPL)"
          className="rounded border border-border bg-background px-2 py-1.5 text-sm w-40"
        />
        <button type="submit" className="rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground">이동</button>
        {score && (
          <>
            <span className="text-xl font-black text-foreground ml-2">{score.ticker}</span>
            <span className="text-sm text-muted-foreground">{score.company_name}</span>
            <div className="ml-auto bg-blue-100 text-blue-800 rounded-md px-3 py-1 text-sm font-bold">
              종합 {composite?.toFixed(2) ?? "—"}
              {composite !== null && (
                <span className="text-xs text-muted-foreground ml-1">
                  / 상위 {Math.round((1 - composite) * 100)}%
                </span>
              )}
            </div>
          </>
        )}
        {isLoading && <span className="text-sm text-muted-foreground">로딩 중...</span>}
      </form>

      {score && (
        <div className="flex gap-4 items-start">
          {/* 좌측: 레이더 + 팩터바 + 재무지표 */}
          <div className="flex-1 min-w-0 flex flex-col gap-4">
            {/* 레이더 + 팩터바 */}
            <div className="flex gap-4">
              <div className="w-44 h-44 shrink-0">
                <RadarChart points={radarPoints} />
              </div>
              <div className="flex-1 rounded-lg border border-border bg-background p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
                  팩터별 백분위 (vs S&P 500)
                </p>
                <FactorBars bars={factorBars} />
              </div>
            </div>

            {/* 재무 지표 3×3 그리드 */}
            <div className="rounded-lg border border-border bg-background p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">재무 지표</p>
              <MetricGrid score={score} />
            </div>
          </div>

          {/* 우측: 투자 의견 기록 */}
          <div className="w-52 shrink-0 rounded-lg border border-border bg-background p-4 h-full">
            <NoteForm ticker={score.ticker} />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 오류 없음 (또는 기존 오류만)

- [ ] **Step 3: Commit**

```bash
git add frontend/app/screener/ frontend/app/screener/\[ticker\]/
git commit -m "feat: add screener detail page with radar chart and metric grid"
```

---

## Task 22: E2E 통합 확인

- [ ] **Step 1: 백엔드 서버 실행 중인지 확인**

```bash
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 2: 배치 실행 (첫 실행은 수 분 소요)**

```bash
curl -s -X POST "http://localhost:8000/api/screener/refresh?universe=sp500"
```
Expected: `{"status":"started","universe":"sp500"}` (백그라운드 실행)

- [ ] **Step 3: 5분 후 데이터 확인**

```bash
curl -s "http://localhost:8000/api/screener/scores?universe=sp500" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'{len(d)}개 종목, 샘플: {d[0][\"ticker\"]} pct_momentum={d[0][\"pct_momentum\"]}')
"
```
Expected: `503개 종목, 샘플: AAPL pct_momentum=0.73` (값은 무관)

- [ ] **Step 4: 프론트엔드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npm run dev
```
브라우저에서 `http://localhost:3333/screener` 열어서:
1. 랭킹 테이블 렌더링 확인
2. 슬라이더 조작 시 즉시 순위 변경 확인
3. 종목 행 클릭 시 `/screener/NVDA` 이동 확인
4. 레이더 차트, 팩터 바, 재무 지표 카드 렌더링 확인
5. 메모 저장 후 새로고침 시 유지 확인

- [ ] **Step 5: 최종 커밋**

```bash
git add -A
git commit -m "feat: quant screener system complete — 5-factor dynamic scoring"
```
