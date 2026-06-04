# 성장주 목표주가 컨센서스 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/growth`의 매수 검증 화면에서 미국 FMP와 국내 KIS 목표주가 컨센서스를 같은 형식으로 표시하고, API 한도 초과를 데이터 없음과 구분한다.

**Architecture:** 신규 `core/data/price_target_consensus.py`가 공급원 선택, 하루 캐시, 오류 상태를 담당한다. 성장주 valuation API는 기존 PEG 응답에 공통 컨센서스 응답을 병합하고, frontend 카드는 목표주가와 오류 원인을 함께 보여준다.

**Tech Stack:** Python, requests, FastAPI, Pydantic, pytest, Next.js, React, TypeScript, ESLint

---

## 파일 구조

- Create: `core/data/price_target_consensus.py`
  - FMP/KIS 공급원 어댑터, 국내 최근 6개월 집계, 종목별 하루 캐시, 공급원 제한 캐시
- Create: `tests/test_price_target_consensus.py`
  - 파서, 국내 집계, FMP 한도 초과 차단 테스트
- Modify: `api/models.py`
  - `GrowthValuationOut` 공통 컨센서스 필드 추가
- Modify: `api/routers/growth.py`
  - 기존 valuation 응답에 컨센서스 조회 결과 병합
- Modify: `tests/test_growth_api.py`
  - valuation API 계약과 외부 오류 격리 테스트
- Modify: `frontend/lib/types.ts`
  - `GrowthValuation` 컨센서스 필드 추가
- Modify: `frontend/components/growth/valuation-card.tsx`
  - 목표주가 요약, 출처, 오류 상태 표시

## Task 1: 공급원 어댑터와 캐시

**Files:**
- Create: `core/data/price_target_consensus.py`
- Create: `tests/test_price_target_consensus.py`

- [ ] **Step 1: FMP 정상 응답 파싱 실패 테스트 작성**

`tests/test_price_target_consensus.py`에 다음 계약을 추가한다.

```python
def test_fetch_fmp_returns_common_consensus(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(targets.requests, "get", lambda *args, **kwargs: FakeResponse([
        {"symbol": "AAPL", "targetHigh": 260, "targetLow": 180, "targetConsensus": 230, "targetMedian": 235},
    ]))

    result = targets.fetch_price_target_consensus("AAPL")

    assert result["consensus_status"] == "ok"
    assert result["consensus_source"] == "FMP"
    assert result["target_mean"] == 230
    assert result["target_median"] == 235
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_price_target_consensus.py::test_fetch_fmp_returns_common_consensus -q`

Expected: FAIL because `core.data.price_target_consensus` does not exist.

- [ ] **Step 3: 최소 FMP 어댑터와 종목별 하루 캐시 구현**

`fetch_price_target_consensus(ticker)`가 미국 티커면 FMP `/stable/price-target-consensus`를 호출한다. `consensus_status`, `consensus_message`, `consensus_source`, `retry_after`, 목표주가 필드를 담은 dict를 반환한다. 같은 종목은 같은 날 재호출하지 않는다.

- [ ] **Step 4: FMP 한도 초과 실패 테스트 작성**

```python
def test_fmp_rate_limit_blocks_other_us_tickers_for_same_day(monkeypatch):
    calls = []
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(targets.requests, "get", lambda *args, **kwargs: calls.append(args) or FakeResponse(
        {"Error Message": "Limit Reach. Please upgrade your plan or visit our documentation"}
    ))

    first = targets.fetch_price_target_consensus("MU")
    second = targets.fetch_price_target_consensus("AAPL")

    assert first["consensus_status"] == "rate_limited"
    assert second["consensus_status"] == "rate_limited"
    assert len(calls) == 1
```

- [ ] **Step 5: 실패 확인 후 공급원 단위 제한 캐시 구현**

Run: `uv run pytest tests/test_price_target_consensus.py::test_fmp_rate_limit_blocks_other_us_tickers_for_same_day -q`

Expected before implementation: FAIL because the second ticker triggers another external call.

한도 초과 메시지를 감지하면 당일 FMP 조회를 차단한다. 정확한 초기화 시각이 응답에 없으면 `retry_after=None`으로 반환한다.

- [ ] **Step 6: 국내 최근 6개월 집계 실패 테스트 작성**

```python
def test_aggregate_kis_uses_latest_report_per_broker_within_six_months():
    rows = [
        {"stck_bsop_date": "20260601", "mbcr_name": "키움", "hts_goal_prc": "430000"},
        {"stck_bsop_date": "20260501", "mbcr_name": "키움", "hts_goal_prc": "400000"},
        {"stck_bsop_date": "20260415", "mbcr_name": "KB", "hts_goal_prc": "530000"},
        {"stck_bsop_date": "20251101", "mbcr_name": "OLD", "hts_goal_prc": "900000"},
    ]

    result = targets.aggregate_kis_reports(rows, today=date(2026, 6, 2))

    assert result["target_mean"] == 480000
    assert result["target_low"] == 430000
    assert result["target_high"] == 530000
    assert result["analyst_count"] == 2
    assert result["consensus_as_of"] == "2026-06-01"
```

- [ ] **Step 7: 실패 확인 후 KIS 어댑터 구현**

Run: `uv run pytest tests/test_price_target_consensus.py::test_aggregate_kis_uses_latest_report_per_broker_within_six_months -q`

Expected before implementation: FAIL because aggregation does not exist.

KIS 기존 `core.prices.kis._get_token`, `_headers`, `KIS_BASE`를 재사용하고 `invest-opinion` API를 조회한다. 최근 6개월, 증권사별 최신 리포트, 양수 목표주가만 집계한다.

- [ ] **Step 8: 공급원 어댑터 테스트 실행**

Run: `uv run pytest tests/test_price_target_consensus.py -q`

Expected: PASS

## Task 2: Growth Valuation API 병합

**Files:**
- Modify: `api/models.py`
- Modify: `api/routers/growth.py`
- Modify: `tests/test_growth_api.py`

- [ ] **Step 1: valuation 공통 응답 실패 테스트 작성**

기존 `test_growth_valuation_returns_consensus_metrics`에서 `fetch_price_target_consensus`를 패치하고 다음 필드를 검증한다.

```python
assert body["consensus_status"] == "ok"
assert body["consensus_source"] == "FMP"
assert body["target_mean"] == 230.0
assert body["upside_pct"] == 15.0
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_growth_api.py::test_growth_valuation_returns_consensus_metrics -q`

Expected: FAIL because valuation response does not include price target fields.

- [ ] **Step 3: API 모델과 라우터 병합 구현**

`GrowthValuationOut`에 spec의 공통 필드를 nullable로 추가한다. `get_valuation()`은 기존 quant row 응답에 `fetch_price_target_consensus(ticker)` 결과를 병합한다. 외부 공급원 오류는 상태 dict로 반환하므로 기존 PEG 응답을 깨지 않는다.

- [ ] **Step 4: 오류 격리 테스트 작성**

```python
def test_growth_valuation_keeps_peg_when_target_consensus_is_rate_limited(client):
    ...
    assert body["peg"] == 0.8
    assert body["consensus_status"] == "rate_limited"
```

- [ ] **Step 5: API 테스트 실행**

Run: `uv run pytest tests/test_growth_api.py -q`

Expected: PASS

## Task 3: 매수 검증 UI 표시

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/growth/valuation-card.tsx`

- [ ] **Step 1: 타입 확장**

`GrowthValuation`에 API 공통 필드를 추가한다.

```ts
consensus_status: "ok" | "no_data" | "rate_limited" | "temporary_error" | "missing_key";
consensus_message: string | null;
consensus_source: "FMP" | "KIS" | null;
retry_after: string | null;
current_price: number | null;
target_mean: number | null;
target_median: number | null;
target_low: number | null;
target_high: number | null;
upside_pct: number | null;
analyst_count: number | null;
consensus_as_of: string | null;
```

- [ ] **Step 2: 목표주가 영역 구현**

`ValuationCard`의 기존 밸류에이션 행 아래에 `PRICE TARGET CONSENSUS` 구역을 추가한다.

- `ok`: 평균 목표주가와 상승 여력을 강조하고 나머지 항목을 행으로 표시
- `no_data`: `최근 6개월 내 목표주가 데이터 없음`
- `rate_limited`: 공급원 이름과 함께 `API 한도를 초과했습니다. 다음 한도 초기화 이후 다시 조회할 수 있습니다.`
- `temporary_error`: `API 조회 제한 또는 일시 오류입니다. 잠시 후 다시 시도해 주세요.`
- `missing_key`: `API 키가 설정되지 않았습니다.`

- [ ] **Step 3: frontend lint 실행**

Run: `cd frontend && npx eslint components/growth/valuation-card.tsx lib/types.ts`

Expected: PASS

## Task 4: 통합 검증

**Files:**
- Verify only

- [ ] **Step 1: Backend 회귀 테스트**

Run: `uv run pytest tests/test_price_target_consensus.py tests/test_growth_api.py tests/test_technical_timing.py tests/test_growth_repository.py tests/test_growth_scorer.py -q`

Expected: PASS

- [ ] **Step 2: Frontend lint**

Run: `cd frontend && npx eslint app/growth/page.tsx components/growth lib/api.ts lib/types.ts`

Expected: PASS

- [ ] **Step 3: 공백 검사**

Run: `git diff --check`

Expected: PASS

- [ ] **Step 4: 실제 API 시나리오**

로그인 후 `AAPL`과 `005930.KS`의 valuation API를 호출한다. 응답에서 기존 PEG와 컨센서스 상태가 함께 반환되는지 확인한다. 키 값은 출력하지 않는다.

- [ ] **Step 5: 브라우저 실제 시나리오**

`http://localhost:3333/growth`에서 미국 종목과 국내 종목을 선택하고 `03 매수 검증` 카드에 목표주가 또는 명확한 상태 안내가 보이는지 확인한다.

