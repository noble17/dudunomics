# Growth Timing Explanation And Consensus Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 단계형 거래량·Wilder RSI·관망 하향 사유를 `/growth`에 표시하고, 미국 목표주가 조회에 무료 Finviz·StockAnalysis fallback을 추가한다.

**Architecture:** `core/scoring/technical_timing.py`가 설명 가능한 타이밍 판정의 canonical source가 된다. `core/data/price_target_consensus.py`는 미국 종목에 대해 FMP, 기존 Finviz 상세 페이지, StockAnalysis forecast 페이지를 순차 조회하고, API와 UI는 provider 상태와 fallback 사용 여부를 노출한다.

**Tech Stack:** Python, pandas, FastAPI, Pydantic, pytest, Next.js, TypeScript, ESLint

---

### Task 1: 단계형 거래량과 Wilder RSI 순수 계산

**Files:**
- Modify: `core/scoring/technical_timing.py`
- Test: `tests/test_technical_timing.py`

- [ ] 합성 OHLCV fixture를 추가하고 `volume_ratio`, `volume_level`, `volume_direction`, `rsi14`, `rsi_level` 기대값을 검증하는 실패 테스트를 작성한다.
- [ ] `uv run pytest tests/test_technical_timing.py -q`를 실행해 신규 필드 부재로 실패하는지 확인한다.
- [ ] `technical_timing.py`에 `_volume_level`, `_volume_direction`, `_wilder_rsi` 순수 함수를 추가한다. RSI는 `ewm(alpha=1 / 14, adjust=False)`로 Wilder smoothing을 적용한다.
- [ ] `analyze_frame`에서 당일을 제외한 직전 20거래일 평균과 당일 거래량 비율을 계산해 신규 필드를 반환한다.

```python
volume_ratio = latest_volume / avg_volume20 if avg_volume20 > 0 else None
volume_level = _volume_level(volume_ratio)
volume_direction = _volume_direction(latest_open, latest_close)
rsi14 = float(_wilder_rsi(close, 14).iloc[-1])
```

- [ ] `uv run pytest tests/test_technical_timing.py -q`를 실행해 통과시킨다.

### Task 2: 최근 5일 위험 신호와 설명 가능한 하향

**Files:**
- Modify: `core/scoring/technical_timing.py`
- Test: `tests/test_technical_timing.py`

- [ ] 당일 음봉 `1.0배`, 최근 5일 음봉 `1.5배`, RSI `80` 이상 fixture를 각각 추가한다.
- [ ] 각 fixture가 `warning_reasons`, `downgrade_reasons`, `watch` 상태를 반환해야 한다는 실패 테스트를 작성한다.
- [ ] reason 항목을 `{code, message, severity}` 구조로 생성하는 작은 helper를 추가한다.
- [ ] 기본 `suitable` 조건을 `aligned AND pullback AND bullish volume_ratio >= 1.0`으로 변경한다.
- [ ] `extreme_rsi`, `bearish_volume`, `recent_bearish_volume_spike`가 존재하면 `suitable` 후보를 `watch`로 하향한다.

```python
base_suitable = aligned and pullback and volume_direction == "bullish" and volume_ratio >= 1.0
downgrade_reasons = [
    reason
    for reason in warning_reasons
    if reason["code"] in {"extreme_rsi", "bearish_volume", "recent_bearish_volume_spike"}
]
status = "watch" if base_suitable and downgrade_reasons else "suitable" if base_suitable else "watch" if aligned else "unsuitable"
```

- [ ] 기존 `volume_explosion`은 `bullish AND volume_ratio >= 1.5`로 유지하고, `uv run pytest tests/test_technical_timing.py -q`를 실행한다.

### Task 3: 타이밍 API 계약 확장

**Files:**
- Modify: `api/models.py`
- Modify: `api/routers/growth.py`
- Modify: `frontend/lib/types.ts`
- Test: `tests/test_growth_api.py`

- [ ] `GrowthTimingOut`과 `GrowthTiming`에 거래량 단계, 방향, 배율, 최근 5일 경고, RSI, reason 배열 필드를 추가하는 계약 테스트를 작성한다.
- [ ] Top10 응답에도 `timing_volume_level`, `timing_rsi_level`, `timing_downgrade_reasons`가 포함되는 실패 테스트를 작성한다.
- [ ] Pydantic 모델, `_with_timing`, TypeScript type을 신규 계약에 맞춰 확장한다.

```python
class TimingReasonOut(BaseModel):
    code: str
    message: str
    severity: str

class GrowthTimingOut(BaseModel):
    volume_ratio: float | None = None
    volume_level: str | None = None
    volume_direction: str | None = None
    recent_bearish_volume_spike: bool | None = None
    rsi14: float | None = None
    rsi_level: str | None = None
    positive_reasons: list[TimingReasonOut] = Field(default_factory=list)
    warning_reasons: list[TimingReasonOut] = Field(default_factory=list)
    downgrade_reasons: list[TimingReasonOut] = Field(default_factory=list)
```

- [ ] 기존 `signal=volume`은 `aligned AND bullish volume_ratio >= 1.0` 의미로 변경한다.
- [ ] `uv run pytest tests/test_growth_api.py tests/test_technical_timing.py -q`를 실행한다.

### Task 4: Timing Card에 하향 사유 표시

**Files:**
- Modify: `frontend/components/growth/timing-card.tsx`
- Modify: `frontend/components/growth/top10-panel.tsx`

- [ ] `TIMING CHECK`에 현재 거래량, 직전 20일 평균, 배율, 거래량 단계, RSI 14를 표시한다.
- [ ] 긍정 신호와 주의 신호를 구분해 표시한다.
- [ ] `downgrade_reasons`가 존재하면 `관망 전환 사유` 박스를 표시한다.

```tsx
{data?.downgrade_reasons?.length ? (
  <div className="rounded border border-fall/30 bg-fall/5 p-3">
    <p className="text-xs font-medium text-fall">관망 전환 사유</p>
    {data.downgrade_reasons.map((reason) => <p key={reason.code}>{reason.message}</p>)}
  </div>
) : null}
```

- [ ] Top10 badge는 `거래량 증가`, `강한 거래량`, `매도 압력`을 구분한다.
- [ ] `cd frontend && npx eslint components/growth/timing-card.tsx components/growth/top10-panel.tsx lib/types.ts`를 실행한다.

### Task 5: 무료 목표주가 fallback

**Files:**
- Modify: `core/data/price_target_consensus.py`
- Test: `tests/test_price_target_consensus.py`

- [ ] Finviz snapshot의 `Target Price`를 canonical 목표주가 구조로 변환하는 실패 테스트를 작성한다.
- [ ] FMP 정상 응답이면 fallback을 호출하지 않는 테스트를 작성한다.
- [ ] FMP가 `subscription_limited`, `no_data`, `rate_limited`, `temporary_error`, `missing_key`이면 Finviz를 호출하는 parametrized 테스트를 작성한다.
- [ ] Finviz도 실패하면 StockAnalysis forecast 페이지를 저빈도로 조회하는 테스트를 작성한다.
- [ ] 모든 provider가 실패하면 `consensus_attempts`에 각 `{source, status}`가 남는 테스트를 작성한다.
- [ ] `_fetch_finviz_target`, `_fetch_stockanalysis_target`, `_fetch_us_consensus`를 추가하고 미국 종목 분기를 `_fetch_us_consensus`로 연결한다.

```python
def _fetch_us_consensus(ticker: str) -> dict:
    primary = _fetch_fmp(ticker)
    if primary["consensus_status"] == "ok":
        return {**primary, "fallback_used": False, "consensus_attempts": [_attempt(primary)]}
    finviz = _fetch_finviz_target(ticker)
    if finviz["consensus_status"] == "ok":
        return {**finviz, "fallback_used": True, "consensus_attempts": [_attempt(primary), _attempt(finviz)]}
    stockanalysis = _fetch_stockanalysis_target(ticker)
    attempts = [_attempt(primary), _attempt(finviz), _attempt(stockanalysis)]
    return {**stockanalysis, "fallback_used": True, "consensus_attempts": attempts}
```

- [ ] 응답에 `fallback_used`, `consensus_attempts`를 추가하고 provider별 종목 캐시와 전역 rate limit 상태를 분리한다.
- [ ] `uv run pytest tests/test_price_target_consensus.py -q`를 실행한다.

### Task 6: 목표주가 API와 UI fallback 상태 표시

**Files:**
- Modify: `api/models.py`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/growth/valuation-card.tsx`
- Test: `tests/test_growth_api.py`

- [ ] valuation 응답에 `fallback_used`, `consensus_attempts`가 보존되는 계약 테스트를 작성한다.
- [ ] `GrowthValuationOut`과 `GrowthValuation`을 확장한다.

```python
class ConsensusAttemptOut(BaseModel):
    source: str
    status: str

class GrowthValuationOut(BaseModel):
    fallback_used: bool = False
    consensus_attempts: list[ConsensusAttemptOut] = Field(default_factory=list)
```

- [ ] 목표주가 카드에서 실제 source를 표시하고 fallback이면 `FMP 제한 -> Finviz 대체 조회` 안내를 표시한다.
- [ ] 모든 provider가 실패하면 각 source의 상태를 한 줄씩 표시한다.
- [ ] `uv run pytest tests/test_growth_api.py tests/test_price_target_consensus.py -q`를 실행한다.
- [ ] `cd frontend && npx eslint components/growth/valuation-card.tsx lib/types.ts`를 실행한다.

### Task 7: 회귀 및 실제 시나리오 검증

**Files:**
- Verify only

- [ ] `uv run pytest tests/test_technical_timing.py tests/test_price_target_consensus.py tests/test_growth_api.py tests/test_growth_repository.py tests/test_growth_scorer.py -q`를 실행한다.
- [ ] `cd frontend && npx eslint app/growth/page.tsx components/growth lib/api.ts lib/types.ts`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] 로컬 API에서 FMP 정상 종목, MU, 국내 종목을 조회해 source와 fallback 상태를 확인한다.
- [ ] 브라우저에서 `/growth`를 열고 거래량 단계, RSI, 주의 신호, 관망 전환 사유, 목표주가 fallback 안내를 직접 확인한다.
