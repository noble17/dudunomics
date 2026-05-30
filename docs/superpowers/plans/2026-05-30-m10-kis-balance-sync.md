# M10: KIS 계좌 잔고 동기화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KIS 실계좌 잔고(국내+미장)를 수동 버튼 클릭으로 앱 holdings에 동기화한다.

**Architecture:** `core/prices/kis.py`에 잔고 조회 순수 함수 2개 추가 → `api/routers/holdings.py`에 `POST /api/holdings/sync-from-kis` 엔드포인트 추가 → `PositionsPanel.tsx` 헤더에 동기화 버튼 + 인라인 토스트 추가. 기존 holdings는 삭제하지 않고, KIS 잔고 종목만 upsert한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, requests, Next.js 16, TypeScript, Tailwind CSS, lucide-react

---

## 파일 변경 목록

| 파일 | 변경 |
|------|------|
| `tests/test_kis_balance.py` | 신규 — 잔고 함수 6개 테스트 |
| `core/prices/kis.py` | `fetch_balance_domestic()` + `fetch_balance_overseas()` 추가 |
| `api/models.py` | `SyncResult` 모델 추가 |
| `api/routers/holdings.py` | `POST /api/holdings/sync-from-kis` 엔드포인트 추가 |
| `frontend/lib/api.ts` | `holdingsApi.syncFromKis()` 추가 |
| `frontend/components/terminal/widgets/PositionsPanel.tsx` | "KIS 동기화" 버튼 + 인라인 토스트 |

---

### Task 1: 잔고 조회 함수 테스트 작성 (TDD Red)

**Files:**
- Create: `tests/test_kis_balance.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_kis_balance.py
"""KIS 잔고 조회 함수 테스트 — 외부 HTTP 호출 없음 (mock)."""
from unittest.mock import MagicMock, patch

import pytest


def _domestic_resp(output1: list[dict]) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": output1,
        "output2": {},
        "output3": {"ctx_area_fk100": "", "ctx_area_nk100": ""},
    }
    m.headers = {"tr_cont": " "}  # 더 이상 페이지 없음
    return m


def _overseas_resp(output1: list[dict]) -> MagicMock:
    m = MagicMock()
    m.json.return_value = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": output1,
        "output2": {},
    }
    m.headers = {"tr_cont": " "}
    return m


class TestFetchBalanceDomestic:
    def test_success(self):
        """정상 응답 → ticker=005930.KS, quantity, avg_price 확인."""
        output1 = [{"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "10", "pchs_avg_pric": "70000"}]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_domestic_resp(output1)):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert len(result) == 1
        item = result[0]
        assert item["ticker"] == "005930.KS"
        assert item["name"] == "삼성전자"
        assert item["quantity"] == 10.0
        assert item["avg_price"] == 70000.0
        assert item["currency"] == "KRW"
        assert item["market"] == "KRX"

    def test_empty_output(self):
        """output1=[] → 빈 리스트."""
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_domestic_resp([])):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert result == []

    def test_no_token_returns_empty(self):
        """토큰 없음 → 빈 리스트."""
        with patch("core.prices.kis._get_token", return_value=None):
            from core.prices.kis import fetch_balance_domestic
            result = fetch_balance_domestic()

        assert result == []


class TestFetchBalanceOverseas:
    def test_success_with_market_conversion(self):
        """NASD → NASDAQ market 변환 + 정상 필드 반환."""
        output1 = [
            {
                "ovrs_pdno": "AAPL",
                "ovrs_item_name": "Apple Inc",
                "ovrs_cblc_qty": "5",
                "pchs_avg_pric": "185.0",
                "ovrs_excg_cd": "NASD",
            }
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_overseas_resp(output1)):
            from core.prices.kis import fetch_balance_overseas
            result = fetch_balance_overseas()

        assert len(result) == 1
        item = result[0]
        assert item["ticker"] == "AAPL"
        assert item["name"] == "Apple Inc"
        assert item["quantity"] == 5.0
        assert item["avg_price"] == 185.0
        assert item["currency"] == "USD"
        assert item["market"] == "NASDAQ"

    def test_skips_zero_quantity(self):
        """ovrs_cblc_qty=0 인 종목은 결과에서 제외."""
        output1 = [
            {"ovrs_pdno": "TSLA", "ovrs_item_name": "Tesla", "ovrs_cblc_qty": "0",
             "pchs_avg_pric": "200.0", "ovrs_excg_cd": "NASD"},
            {"ovrs_pdno": "MSFT", "ovrs_item_name": "Microsoft", "ovrs_cblc_qty": "3",
             "pchs_avg_pric": "420.0", "ovrs_excg_cd": "NASD"},
        ]
        with patch("core.prices.kis._get_token", return_value="fake"), \
             patch("core.prices.kis.requests.get", return_value=_overseas_resp(output1)):
            from core.prices.kis import fetch_balance_overseas
            result = fetch_balance_overseas()

        assert len(result) == 1
        assert result[0]["ticker"] == "MSFT"
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_kis_balance.py -v 2>&1 | tail -20
```

예상: `ImportError` 또는 `AttributeError: module 'core.prices.kis' has no attribute 'fetch_balance_domestic'`

---

### Task 2: 잔고 조회 함수 구현

**Files:**
- Modify: `core/prices/kis.py` (파일 끝에 추가)

- [ ] **Step 1: `fetch_balance_domestic` + `fetch_balance_overseas` 함수 추가**

`core/prices/kis.py` 파일 끝 (639행 이후)에 다음을 추가:

```python
# ── 계좌 잔고 조회 (모듈 레벨 함수) ────────────────────────────────────────────

_EXCD_TO_MARKET_BALANCE: dict[str, str] = {
    "NASD": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX",
    "NAS":  "NASDAQ", "NYS":  "NYSE", "AMS":  "AMEX",
}

_CANO = "63241945"
_ACNT_PRDT_CD = "01"


def fetch_balance_domestic() -> list[dict]:
    """KIS 국내 계좌 잔고 조회. 토큰 없음 or 오류 시 빈 리스트."""
    token = _get_token()
    if not token:
        return []

    results: list[dict] = []
    ctx_fk = ""
    ctx_nk = ""

    for _ in range(10):
        res = requests.get(
            f"{KIS_BASE}/uapi/domestic-stock/v1/trading/inquire-balance",
            params={
                "CANO": _CANO,
                "ACNT_PRDT_CD": _ACNT_PRDT_CD,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "05",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": ctx_fk,
                "CTX_AREA_NK100": ctx_nk,
            },
            headers=_headers("TTTC8434R", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            log.warning("KIS 국내 잔고 오류: %s", data.get("msg1"))
            break

        for item in data.get("output1") or []:
            qty = float(item.get("hldg_qty") or 0)
            if qty <= 0:
                continue
            code = item.get("pdno", "")
            results.append({
                "ticker": f"{code}.KS",
                "name": item.get("prdt_name") or code,
                "quantity": qty,
                "avg_price": float(item.get("pchs_avg_pric") or 0),
                "currency": "KRW",
                "market": "KRX",
            })

        tr_cont = res.headers.get("tr_cont", " ")
        if tr_cont not in ("F", "M"):
            break
        output3 = data.get("output3") or {}
        ctx_fk = output3.get("ctx_area_fk100", "")
        ctx_nk = output3.get("ctx_area_nk100", "")

    return results


def fetch_balance_overseas() -> list[dict]:
    """KIS 해외 계좌 잔고 조회 (전 거래소). 토큰 없음 or 오류 시 빈 리스트."""
    token = _get_token()
    if not token:
        return []

    results: list[dict] = []
    ctx_fk = ""
    ctx_nk = ""

    for _ in range(10):
        res = requests.get(
            f"{KIS_BASE}/uapi/overseas-stock/v1/trading/inquire-balance",
            params={
                "CANO": _CANO,
                "ACNT_PRDT_CD": _ACNT_PRDT_CD,
                "OVRS_EXCG_CD": "__ALL__",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": ctx_fk,
                "CTX_AREA_NK200": ctx_nk,
            },
            headers=_headers("TTTS3012R", token),
            timeout=10,
        )
        data = res.json()
        if data.get("rt_cd") != "0":
            log.warning("KIS 해외 잔고 오류: %s", data.get("msg1"))
            break

        for item in data.get("output1") or []:
            qty = float(item.get("ovrs_cblc_qty") or 0)
            if qty <= 0:
                continue
            excd = item.get("ovrs_excg_cd", "")
            market = _EXCD_TO_MARKET_BALANCE.get(excd, excd)
            results.append({
                "ticker": item.get("ovrs_pdno", ""),
                "name": item.get("ovrs_item_name") or item.get("ovrs_pdno", ""),
                "quantity": qty,
                "avg_price": float(item.get("pchs_avg_pric") or 0),
                "currency": "USD",
                "market": market,
            })

        tr_cont = res.headers.get("tr_cont", " ")
        if tr_cont not in ("F", "M"):
            break
        output2 = data.get("output2") or {}
        ctx_fk = output2.get("ctx_area_fk200", "")
        ctx_nk = output2.get("ctx_area_nk200", "")

    return results
```

- [ ] **Step 2: 테스트 실행 → PASS 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_kis_balance.py -v 2>&1 | tail -20
```

예상: `6 passed`

- [ ] **Step 3: 커밋**

```bash
git add core/prices/kis.py tests/test_kis_balance.py
git commit -m "feat(m10): KIS 국내/해외 잔고 조회 함수 추가 + 테스트 6개"
```

---

### Task 3: SyncResult 모델 + 동기화 엔드포인트

**Files:**
- Modify: `api/models.py`
- Modify: `api/routers/holdings.py`
- Modify: `tests/test_kis_balance.py` (엔드포인트 테스트 2개 추가)

- [ ] **Step 1: `SyncResult` 모델을 `api/models.py` 끝에 추가**

`api/models.py` 파일 끝(350행 이후)에 추가:

```python
class SyncResult(BaseModel):
    added: int
    updated: int
    errors: list[str]
```

- [ ] **Step 2: 엔드포인트 테스트 2개를 `tests/test_kis_balance.py`에 추가**

`test_kis_balance.py` 파일 끝에 다음 클래스를 추가:

```python
class TestSyncEndpoint:
    def test_upserts_holdings(self, client, monkeypatch):
        """잔고 mock → upsert_holding 호출 횟수·인자 검증."""
        domestic = [
            {"ticker": "005930.KS", "name": "삼성전자", "quantity": 10.0,
             "avg_price": 70000.0, "currency": "KRW", "market": "KRX"},
        ]
        overseas = [
            {"ticker": "AAPL", "name": "Apple Inc", "quantity": 5.0,
             "avg_price": 185.0, "currency": "USD", "market": "NASDAQ"},
        ]
        monkeypatch.setattr("api.routers.holdings.fetch_balance_domestic", lambda: domestic)
        monkeypatch.setattr("api.routers.holdings.fetch_balance_overseas", lambda: overseas)

        res = client.post("/api/holdings/sync-from-kis")
        assert res.status_code == 200
        body = res.json()
        assert body["added"] == 2
        assert body["updated"] == 0
        assert body["errors"] == []

        holdings = client.get("/api/holdings").json()
        tickers = {h["ticker"] for h in holdings}
        assert "005930.KS" in tickers
        assert "AAPL" in tickers

    def test_no_token_returns_error(self, client, monkeypatch):
        """잔고 함수가 빈 리스트 반환 시 errors 포함 200 응답."""
        monkeypatch.setattr("api.routers.holdings.fetch_balance_domestic", lambda: [])
        monkeypatch.setattr("api.routers.holdings.fetch_balance_overseas", lambda: [])

        res = client.post("/api/holdings/sync-from-kis")
        assert res.status_code == 200
        body = res.json()
        assert body["added"] == 0
        assert body["updated"] == 0
        assert len(body["errors"]) > 0
```

- [ ] **Step 3: 엔드포인트 테스트 실행 → FAIL 확인 (엔드포인트 미구현)**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_kis_balance.py::TestSyncEndpoint -v 2>&1 | tail -20
```

예상: `FAILED` (404 또는 ImportError)

- [ ] **Step 4: 동기화 엔드포인트를 `api/routers/holdings.py`에 추가**

`api/routers/holdings.py` 파일 상단 import를 수정:

```python
from api.models import CashUpdate, HoldingIn, HoldingOut, TickerLookupOut, TickerSearchHit, TargetWeightUpdate, SyncResult
from core.prices.kis import fetch_balance_domestic, fetch_balance_overseas
```

기존 import 라인:
```python
from api.models import CashUpdate, HoldingIn, HoldingOut, TickerLookupOut, TickerSearchHit, TargetWeightUpdate
```

그리고 `_backup_json` 함수 앞(104행 이전)에 엔드포인트 추가:

```python
@router.post("/sync-from-kis", response_model=SyncResult)
def sync_from_kis(user: CurrentUser = Depends(current_user)):
    existing = {h["ticker"] for h in repo.get_holdings(user.id)}
    added, updated, errors = 0, 0, []

    domestic = fetch_balance_domestic()
    overseas = fetch_balance_overseas()

    if not domestic and not overseas:
        errors.append("KIS 인증 실패 또는 잔고 없음")
        return SyncResult(added=0, updated=0, errors=errors)

    for item in domestic + overseas:
        try:
            repo.upsert_holding(user_id=user.id, **item)
            if item["ticker"] in existing:
                updated += 1
            else:
                added += 1
        except Exception as e:
            errors.append(f"{item['ticker']}: {e}")

    return SyncResult(added=added, updated=updated, errors=errors)
```

- [ ] **Step 5: 전체 테스트 실행 → 모두 PASS**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/test_kis_balance.py -v 2>&1 | tail -20
```

예상: `8 passed` (기존 6 + 엔드포인트 2)

- [ ] **Step 6: 기존 holdings 테스트 회귀 없는지 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/ -v 2>&1 | tail -10
```

예상: 전체 통과

- [ ] **Step 7: 커밋**

```bash
git add api/models.py api/routers/holdings.py tests/test_kis_balance.py
git commit -m "feat(m10): SyncResult 모델 + POST /api/holdings/sync-from-kis 엔드포인트"
```

---

### Task 4: 프론트엔드 — API 함수 + 동기화 버튼

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/terminal/widgets/PositionsPanel.tsx`

참고: 이 프로젝트는 Next.js 16 (breaking changes 있음). 수정 전 `node_modules/next/dist/docs/` 가이드 참고.

- [ ] **Step 1: `holdingsApi`에 `syncFromKis` 추가**

`frontend/lib/api.ts`의 `holdingsApi` 객체 내 `search` 줄 다음에 추가:

기존:
```typescript
  search: (q: string) =>
    request<TickerSearchHit[]>(`/api/holdings/search?q=${encodeURIComponent(q)}`),
};
```

변경:
```typescript
  search: (q: string) =>
    request<TickerSearchHit[]>(`/api/holdings/search?q=${encodeURIComponent(q)}`),
  syncFromKis: () =>
    request<{ added: number; updated: number; errors: string[] }>(
      "/api/holdings/sync-from-kis",
      { method: "POST" }
    ),
};
```

- [ ] **Step 2: `PositionsPanel.tsx`에 동기화 버튼 + 토스트 추가**

`frontend/components/terminal/widgets/PositionsPanel.tsx` 전체를 다음으로 교체:

```tsx
"use client";
import { useState } from "react";
import useSWR from "swr";
import { RefreshCw } from "lucide-react";
import { portfolioApi, holdingsApi } from "@/lib/api";

interface Props {
  onTickerSelect?: (ticker: string) => void;
  selectedTicker?: string;
}

interface SyncToast {
  id: number;
  message: string;
  isError: boolean;
}

let _toastId = 0;

export function PositionsPanel({ onTickerSelect, selectedTicker }: Props) {
  const { data: snapshot, isLoading, mutate } = useSWR(
    "/api/portfolio/current",
    portfolioApi.current,
    { refreshInterval: 30_000 }
  );
  const [syncing, setSyncing] = useState(false);
  const [toasts, setToasts] = useState<SyncToast[]>([]);

  function showToast(message: string, isError = false) {
    const id = ++_toastId;
    setToasts((prev) => [...prev, { id, message, isError }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await holdingsApi.syncFromKis();
      if (result.errors.length > 0) {
        showToast(`동기화 오류: ${result.errors[0]}`, true);
      } else {
        showToast(`KIS 동기화 완료 — 추가 ${result.added}개, 수정 ${result.updated}개`);
      }
      mutate();
    } catch {
      showToast("KIS 동기화 실패", true);
    } finally {
      setSyncing(false);
    }
  }

  if (isLoading) return (
    <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">로딩 중…</div>
  );
  if (!snapshot?.rows.length) return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0 flex items-center justify-between">
        <span>POSITIONS</span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[8px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={9} className={syncing ? "animate-spin" : ""} />
          KIS
        </button>
      </div>
      <div className="p-3 text-[10px] font-mono text-[var(--color-text-muted)]">보유 종목 없음</div>
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-3 py-2 text-[10px] font-mono shadow-lg border ${
              t.isError
                ? "bg-[var(--color-bg-secondary)] border-red-500 text-red-400"
                : "bg-[var(--color-bg-secondary)] border-[var(--color-primary)] text-[var(--color-text-primary)]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );

  const realizedPnl = (snapshot as any).realized_pnl_krw ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 토스트 */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-1.5 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-3 py-2 text-[10px] font-mono shadow-lg border ${
              t.isError
                ? "bg-[var(--color-bg-secondary)] border-red-500 text-red-400"
                : "bg-[var(--color-bg-secondary)] border-[var(--color-primary)] text-[var(--color-text-primary)]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>

      {/* 헤더 */}
      <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0 flex items-center justify-between">
        <span>POSITIONS</span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[8px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:border-[var(--color-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={9} className={syncing ? "animate-spin" : ""} />
          KIS
        </button>
      </div>

      {/* 종목 리스트 */}
      <div className="flex-1 overflow-auto">
        <div className="px-3 py-1">
          <div className="grid grid-cols-3 text-[9px] font-mono text-[var(--color-text-muted)] mb-1 uppercase">
            <span>Ticker</span>
            <span className="text-right">수익률</span>
            <span className="text-right">평가액</span>
          </div>
          {snapshot.rows.map((row) => (
            <div
              key={row.ticker}
              onClick={() => onTickerSelect?.(row.ticker)}
              className={`grid grid-cols-3 py-1 border-b border-[var(--color-border)] cursor-pointer hover:bg-[var(--color-bg-tertiary)] text-[10px] font-mono ${
                selectedTicker === row.ticker ? "bg-[var(--color-bg-tertiary)]" : ""
              }`}
            >
              <span className="text-[var(--color-text-primary)]">{row.ticker}</span>
              <span className={`text-right ${row.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                {row.return_pct >= 0 ? "+" : ""}{row.return_pct.toFixed(1)}%
              </span>
              <span className="text-right text-[var(--color-text-secondary)]">
                ₩{(row.market_value_krw / 1_000_000).toFixed(1)}M
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 하단 요약 */}
      <div className="px-3 py-2 border-t border-[var(--color-border)] shrink-0 space-y-0.5">
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">총 평가</span>
          <span className="text-[var(--color-text-primary)]">
            ₩{(snapshot.total_equity_krw / 1_000_000).toFixed(1)}M
          </span>
        </div>
        <div className="flex justify-between text-[10px] font-mono">
          <span className="text-[var(--color-text-muted)]">실현 손익</span>
          <span className={realizedPnl >= 0 ? "text-green-400" : "text-red-400"}>
            {realizedPnl >= 0 ? "+" : ""}₩{(realizedPnl / 10_000).toFixed(0)}만
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript 타입 체크**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx tsc --noEmit 2>&1 | head -30
```

예상: 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/lib/api.ts frontend/components/terminal/widgets/PositionsPanel.tsx
git commit -m "feat(m10): PositionsPanel에 KIS 동기화 버튼 + 토스트 추가"
```

---

### Task 5: 최종 검증

- [ ] **Step 1: 전체 테스트 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics && .venv/bin/pytest tests/ -v 2>&1 | tail -15
```

예상: 전체 통과 (`test_kis_balance.py` 8개 포함)

- [ ] **Step 2: 프론트엔드 빌드 에러 없음 확인**

```bash
cd /Users/user/Development/private/dudunomics/frontend && npx next build 2>&1 | tail -15
```

예상: `✓ Compiled successfully` 또는 `✓ Build complete`

- [ ] **Step 3: 완료 커밋 (변경 없으면 생략)**

```bash
git log --oneline -5
```

최종 커밋 3개 확인:
1. `feat(m10): KIS 국내/해외 잔고 조회 함수 추가 + 테스트 6개`
2. `feat(m10): SyncResult 모델 + POST /api/holdings/sync-from-kis 엔드포인트`
3. `feat(m10): PositionsPanel에 KIS 동기화 버튼 + 토스트 추가`
