# M3 실시간 시세 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** IndexStrip에 SPY / QQQ / USD/KRW / BTC 실시간 시세(가격 + 등락폭 + 등락률)를 10초 REST 폴링으로 연결한다.

**Architecture:** 단일 `GET /api/quotes` 엔드포인트가 KISPriceProvider(SPY/QQQ), KisFxProvider(USD/KRW), UpbitProvider(BTC)를 순차 호출해 배치 응답을 반환한다. 프론트엔드 `useQuotes` 훅이 10초마다 폴링하고 IndexStrip에 렌더링한다.

**Tech Stack:** Python/FastAPI (백엔드), TypeScript/React/Next.js (프론트), requests (Upbit API 호출), pytest (테스트)

---

## File Map

| 파일 | 변경 |
|---|---|
| `core/prices/upbit.py` | 신규 — UpbitProvider |
| `api/models.py` | 수정 — QuoteItem, QuotesOut 추가 |
| `api/routers/quotes.py` | 신규 — GET /api/quotes |
| `api/main.py` | 수정 — quotes 라우터 등록 |
| `tests/test_quotes_api.py` | 신규 — API 테스트 |
| `frontend/lib/types.ts` | 수정 — QuoteItem, QuotesOut 타입 추가 |
| `frontend/lib/api.ts` | 수정 — quotesApi.get() 추가 |
| `frontend/hooks/useQuotes.ts` | 신규 — 10초 폴링 훅 |
| `frontend/components/terminal/IndexStrip.tsx` | 수정 — 실제 데이터 연결 |

---

### Task 1: UpbitProvider

**Files:**
- Create: `core/prices/upbit.py`

- [ ] **Step 1: `core/prices/upbit.py` 작성**

```python
"""Upbit 공개 REST API — BTC/KRW 현재가 조회 (API 키 불필요)."""
import requests
from core.prices.base import Price


class UpbitProvider:
    _BASE = "https://api.upbit.com/v1"

    def get_btc_krw(self) -> Price:
        res = requests.get(
            f"{self._BASE}/ticker",
            params={"markets": "KRW-BTC"},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()[0]
        current = float(data["trade_price"])
        change_pct = float(data["signed_change_rate"]) * 100
        return Price(
            ticker="BTC",
            current=current,
            currency="KRW",
            change_pct=change_pct,
        )
```

- [ ] **Step 2: 연결 확인 (서버 실행 중일 때)**

```bash
cd /Users/user/Development/private/dudunomics
python -c "from core.prices.upbit import UpbitProvider; p = UpbitProvider(); print(p.get_btc_krw())"
```

Expected: `Price(ticker='BTC', current=151234000.0, currency='KRW', change_pct=2.87)` (숫자는 실시간)

- [ ] **Step 3: 커밋**

```bash
git add core/prices/upbit.py
git commit -m "feat(m3): add UpbitProvider for BTC/KRW quotes"
```

---

### Task 2: QuoteItem / QuotesOut 모델

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: `api/models.py` 하단에 추가**

기존 마지막 모델 아래에 다음을 추가한다:

```python
class QuoteItem(BaseModel):
    price: float
    change_abs: float
    change_pct: float


class QuotesOut(BaseModel):
    SPY: QuoteItem | None = None
    QQQ: QuoteItem | None = None
    USDKRW: QuoteItem | None = None
    BTC: QuoteItem | None = None
```

- [ ] **Step 2: 커밋**

```bash
git add api/models.py
git commit -m "feat(m3): add QuoteItem and QuotesOut models"
```

---

### Task 3: GET /api/quotes 엔드포인트

**Files:**
- Create: `api/routers/quotes.py`
- Modify: `api/main.py`

- [ ] **Step 1: `api/routers/quotes.py` 작성**

```python
import logging
from fastapi import APIRouter, Depends
from core.auth.deps import current_user, CurrentUser
from core.prices.kis import KISPriceProvider
from core.prices.upbit import UpbitProvider
from core.fx import get_fx_provider
from api.models import QuoteItem, QuotesOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])

_kis = KISPriceProvider()
_fx = get_fx_provider()
_upbit = UpbitProvider()


def _make_item(price: float, change_pct: float) -> QuoteItem:
    return QuoteItem(
        price=price,
        change_abs=round(price * change_pct / 100, 4),
        change_pct=round(change_pct, 4),
    )


@router.get("", response_model=QuotesOut)
def get_quotes(user: CurrentUser = Depends(current_user)):
    result = QuotesOut()

    # SPY / QQQ
    try:
        prices = _kis.get_current_prices(["SPY", "QQQ"])
        if "SPY" in prices:
            p = prices["SPY"]
            result.SPY = _make_item(p.current, p.change_pct or 0.0)
        if "QQQ" in prices:
            p = prices["QQQ"]
            result.QQQ = _make_item(p.current, p.change_pct or 0.0)
    except Exception as e:
        log.warning("SPY/QQQ 조회 실패: %s", e)

    # USD/KRW
    try:
        rate = _fx.get_rate("USDKRW")
        result.USDKRW = QuoteItem(price=rate, change_abs=0.0, change_pct=0.0)
    except Exception as e:
        log.warning("USDKRW 조회 실패: %s", e)

    # BTC
    try:
        btc = _upbit.get_btc_krw()
        result.BTC = _make_item(btc.current, btc.change_pct or 0.0)
    except Exception as e:
        log.warning("BTC 조회 실패: %s", e)

    return result
```

- [ ] **Step 2: `api/main.py`에 라우터 등록**

`api/main.py`에서 기존 import 블록 아래에 추가:

```python
from api.routers.quotes import router as quotes_router
```

`app.include_router(workspace_router)` 다음 줄에 추가:

```python
app.include_router(quotes_router)
```

- [ ] **Step 3: 커밋**

```bash
git add api/routers/quotes.py api/main.py
git commit -m "feat(m3): add GET /api/quotes endpoint"
```

---

### Task 4: /api/quotes 테스트

**Files:**
- Create: `tests/test_quotes_api.py`

- [ ] **Step 1: `tests/test_quotes_api.py` 작성**

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from core.prices.base import Price


@pytest.fixture
def quotes_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "q@test.com", "password": "password123"})
    return c


def _mock_kis_prices(tickers, **_):
    return {
        "SPY": Price(ticker="SPY", current=597.42, currency="USD", change_pct=1.23),
        "QQQ": Price(ticker="QQQ", current=519.87, currency="USD", change_pct=-0.45),
    }


def _mock_fx_rate(pair):
    return 1372.5


def _mock_btc():
    return Price(ticker="BTC", current=151234000.0, currency="KRW", change_pct=2.87)


def test_quotes_structure(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    for key in ("SPY", "QQQ", "USDKRW", "BTC"):
        assert key in data
        assert data[key] is not None
        assert "price" in data[key]
        assert "change_abs" in data[key]
        assert "change_pct" in data[key]


def test_quotes_values(quotes_client):
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=_mock_btc),
    ):
        res = quotes_client.get("/api/quotes")
    data = res.json()
    assert data["SPY"]["price"] == pytest.approx(597.42)
    assert data["QQQ"]["change_pct"] == pytest.approx(-0.45)
    assert data["USDKRW"]["price"] == pytest.approx(1372.5)
    assert data["USDKRW"]["change_pct"] == 0.0
    assert data["BTC"]["price"] == pytest.approx(151234000.0)


def test_quotes_partial_failure(quotes_client):
    """BTC 조회 실패해도 SPY/QQQ/USDKRW는 정상 반환."""
    with (
        patch("api.routers.quotes._kis.get_current_prices", side_effect=_mock_kis_prices),
        patch("api.routers.quotes._fx.get_rate", side_effect=_mock_fx_rate),
        patch("api.routers.quotes._upbit.get_btc_krw", side_effect=RuntimeError("Upbit 오류")),
    ):
        res = quotes_client.get("/api/quotes")
    assert res.status_code == 200
    data = res.json()
    assert data["SPY"] is not None
    assert data["BTC"] is None


def test_quotes_requires_auth(fresh_db, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    from api.main import app
    c = TestClient(app)
    res = c.get("/api/quotes")
    assert res.status_code == 401
```

- [ ] **Step 2: 테스트 실행**

```bash
cd /Users/user/Development/private/dudunomics
uv run pytest tests/test_quotes_api.py -v
```

Expected: 4개 테스트 모두 PASS

- [ ] **Step 3: 커밋**

```bash
git add tests/test_quotes_api.py
git commit -m "test(m3): add /api/quotes API tests"
```

---

### Task 5: 프론트엔드 타입 + API 함수

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: `frontend/lib/types.ts` 하단에 추가**

```typescript
export interface QuoteItem {
  price: number
  change_abs: number
  change_pct: number
}

export interface QuotesOut {
  SPY: QuoteItem | null
  QQQ: QuoteItem | null
  USDKRW: QuoteItem | null
  BTC: QuoteItem | null
}
```

- [ ] **Step 2: `frontend/lib/api.ts` import 라인 수정**

파일 최상단 import에 `QuoteItem`, `QuotesOut` 추가:

```typescript
import type {
  BacktestRunIn, BacktestRunOut, CashUpdate, EventOut,
  HoldingIn, HoldingOut, PortfolioSnapshot,
  SnapshotHistory, StrategyDef,
  TickerLookupOut, TickerSearchHit,
  QuantScore, TickerNote,
  WorkspaceLayout,
  QuotesOut,
} from "./types";
```

- [ ] **Step 3: `frontend/lib/api.ts`에 quotesApi 추가**

파일 하단에 추가:

```typescript
export const quotesApi = {
  get: () => request<QuotesOut>("/api/quotes"),
};
```

- [ ] **Step 4: 타입체크**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 5: 커밋**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(m3): add QuotesOut types and quotesApi"
```

---

### Task 6: useQuotes 폴링 훅

**Files:**
- Create: `frontend/hooks/useQuotes.ts`

- [ ] **Step 1: `frontend/hooks/useQuotes.ts` 작성**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";
import { quotesApi } from "@/lib/api";
import type { QuotesOut } from "@/lib/types";

const POLL_INTERVAL_MS = 10_000;

export function useQuotes(): QuotesOut | null {
  const [quotes, setQuotes] = useState<QuotesOut | null>(null);
  const lastRef = useRef<QuotesOut | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      try {
        const data = await quotesApi.get();
        if (!cancelled) {
          lastRef.current = data;
          setQuotes(data);
        }
      } catch {
        // 오류 시 이전 값 유지 (깜빡임 방지)
        if (!cancelled && lastRef.current) {
          setQuotes(lastRef.current);
        }
      }
    }

    fetch();
    const id = setInterval(fetch, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return quotes;
}
```

- [ ] **Step 2: 타입체크**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/hooks/useQuotes.ts
git commit -m "feat(m3): add useQuotes polling hook (10s interval)"
```

---

### Task 7: IndexStrip 실제 데이터 연결

**Files:**
- Modify: `frontend/components/terminal/IndexStrip.tsx`

- [ ] **Step 1: `IndexStrip.tsx` 전체 교체**

```tsx
"use client";

import { useQuotes } from "@/hooks/useQuotes";
import type { QuoteItem } from "@/lib/types";

function fmt(value: number, decimals: number): string {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function QuoteCell({ label, item, decimals }: {
  label: string;
  item: QuoteItem | null | undefined;
  decimals: number;
}) {
  const up = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;
  const changeColor = up
    ? "text-[var(--color-gain)]"
    : down
    ? "text-[var(--color-loss)]"
    : "text-[var(--color-text-secondary)]";
  const arrow = up ? "▲" : down ? "▼" : "";

  return (
    <div className="flex items-center gap-1.5 text-xs shrink-0">
      <span className="text-[var(--color-text-secondary)] font-medium">{label}</span>
      <span className="text-[var(--color-text-primary)] font-mono">
        {item ? fmt(item.price, decimals) : "—"}
      </span>
      {item && (
        <span className={`font-mono text-[10px] ${changeColor}`}>
          {arrow}{item.change_abs >= 0 ? "+" : ""}{fmt(item.change_abs, decimals)}{" "}
          ({item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%)
        </span>
      )}
    </div>
  );
}

export function IndexStrip() {
  const quotes = useQuotes();

  return (
    <div className="flex items-center gap-6 px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0 overflow-x-auto">
      <QuoteCell label="SPY"     item={quotes?.SPY}    decimals={2} />
      <QuoteCell label="QQQ"     item={quotes?.QQQ}    decimals={2} />
      <QuoteCell label="USD/KRW" item={quotes?.USDKRW} decimals={1} />
      <QuoteCell label="BTC"     item={quotes?.BTC}    decimals={0} />
    </div>
  );
}
```

- [ ] **Step 2: 빌드 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/terminal/IndexStrip.tsx
git commit -m "feat(m3): connect IndexStrip to live quotes via useQuotes"
```

---

### Task 8: 브라우저 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 서버 실행 확인**

프론트(`http://localhost:3333`)와 백엔드(`http://localhost:8000`)가 실행 중인지 확인:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:3333 | head -3
```

Expected: `{"status":"ok"}`, HTML 응답

- [ ] **Step 2: gstack-browse로 /terminal 접속 후 IndexStrip 확인**

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"
$B goto http://localhost:3333/terminal
sleep 3
$B screenshot /tmp/m3_indexstrip.png
```

- [ ] **Step 3: 스크린샷 확인**

Read tool로 `/tmp/m3_indexstrip.png` 확인 — IndexStrip에 실제 숫자가 표시되는지 검증:
- `—` 플레이스홀더가 사라졌는지
- 등락률(▲/▼ + %)이 표시되는지
- 색상이 올바른지 (상승=빨강, 하락=파랑)

- [ ] **Step 4: PROGRESS.md 갱신 + 최종 커밋**

`PROGRESS.md`에 M3 섹션 추가:

```markdown
## M3 — IndexStrip 실시간 시세 연결 (2026-05-29)
- [x] UpbitProvider (BTC/KRW)
- [x] GET /api/quotes 배치 엔드포인트
- [x] useQuotes 10초 폴링 훅
- [x] IndexStrip 실제 데이터 연결 (가격 + 등락폭 + 등락률)
- [x] 브라우저 검증
```

```bash
git add PROGRESS.md
git commit -m "docs: M3 완료 체크 PROGRESS.md 갱신"
```
