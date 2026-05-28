# 프로페셔널 멀티 팩터 퀀트 스코어링 시스템 설계 문서

**작성일:** 2026-05-28  
**상태:** 승인됨  
**범위:** 종목 스크리닝 페이지 + 종목 상세 분석 페이지 + 퀀트 연산 백엔드

---

## 1. 시스템 개요

사용자가 5가지 팩터 가중치를 실시간으로 조절하며 S&P 500 유니버스 내 종목을 발굴하고, 개별 종목의 재무·퀀트 지표를 상세 분석하고 투자 메모를 기록하는 시스템.

### 핵심 아키텍처 결정

**클라이언트 사이드 가중치 연산** 채택:
- 서버: 하루 1회 배치로 전체 유니버스 팩터값 계산 → DuckDB 저장
- 프론트엔드: 최초 로드 시 전체 백분위 데이터 수신(~25KB), 슬라이더 조작 시 브라우저에서 즉시 재랭킹
- 이유: 슬라이더 드래그 중 API 호출 방식으로는 "실시간 랭킹 갱신" 체감이 불가능함

---

## 2. 팩터 아키텍처 (Quant Core)

### 2-1. 가격 모멘텀 (Price Momentum)

**정의:** 12-1M 모멘텀 = 직전 12개월 총수익률 − 직전 1개월 수익률

**금융공학적 근거:**  
단순 12개월 수익률은 최근 1개월 급등주를 과포함한다. 행동재무학 연구(Jegadeesh & Titman, 1993)에서 단기 과열 구간은 평균회귀(Mean Reversion) 노이즈를 일으키므로, 직전 1개월을 제거하여 진짜 중기 모멘텀만 포착한다.

**계산:**
```
momentum_raw = price(t-1M) / price(t-12M) - 1
```
OHLCV 캐시(`core/data/ohlcv_cache.py`)에서 월말 종가 사용.

**구현 파일:** `core/factors/price_momentum.py`

---

### 2-2. 펀더멘탈 밸류에이션 (Fundamental Valuation)

**정의:** Forward PER과 PBR을 Z-score 표준화 후 단순평균한 통합 밸류 스코어 (낮을수록 저평가 → 고득점)

**금융공학적 근거:**  
PER 단독은 이익 사이클 왜곡에 취약하고, PBR 단독은 자산경량 기업(기술주)에 불리하다. 두 지표를 Z-score로 표준화 후 결합하면 서로의 약점을 보완한다. 백분위 계산 시 역수 처리(`1 - percentile`)하여 낮은 밸류에이션이 높은 점수를 받도록 한다.

**계산:**
```
z_fwd_pe = (fwd_pe - mean(fwd_pe)) / std(fwd_pe)  # 유니버스 기준
z_pbr    = (pbr - mean(pbr)) / std(pbr)
value_raw = (z_fwd_pe + z_pbr) / 2                # 낮을수록 저평가
```

**구현 파일:** `core/factors/valuation.py` (신규 파일 — 기존 `forward_per.py`는 factor_rebalance·hybrid 전략에서 사용 중이므로 유지하고 별도 신규 파일로 분리)

---

### 2-3. EPS 모멘텀 (Earnings Momentum)

**정의:** 1개월 및 3개월 Forward EPS 추정치 변화율의 가중 평균

**금융공학적 근거:**  
기관 애널리스트의 EPS 추정 상향은 기관 자금 유입 선행지표다. 1개월 변화율은 최신 컨센서스를, 3개월 변화율은 추세 지속성을 반영한다. 두 기간을 결합해 단기 노이즈와 추세 모두 포착.

**계산:**
```
eps_1m = (fwd_eps_now - fwd_eps_1m_ago) / abs(fwd_eps_1m_ago)
eps_3m = (fwd_eps_now - fwd_eps_3m_ago) / abs(fwd_eps_3m_ago)
eps_momentum_raw = 0.5 * eps_1m + 0.5 * eps_3m
```

**구현 파일:** `core/factors/forward_eps_momentum.py` (기존 파일 확장, 3M 추가)

---

### 2-4. 퀄리티 (Quality & Solvency)

**정의:** ROE와 부채비율 역수를 결합한 재무 건전성 스코어. CFO 양수 조건은 하드 필터로도 사용 가능.

**금융공학적 근거:**  
ROE만으로는 레버리지를 통한 회계적 착시를 검출하지 못한다. 부채비율 역수를 결합해 자본효율성과 재무 안정성을 동시에 평가. CFO 양수 조건은 이익의 질 검증 — 영업현금흐름이 마이너스인 기업의 ROE는 회계 조작 가능성이 높다.

**계산:**
```
quality_raw = 0.6 * roe + 0.4 * (1 / max(debt_ratio, 0.01))
cfo_positive = operating_cashflow > 0  # 하드 필터 토글용
```

**구현 파일:** `core/factors/quality.py` (신규)

---

### 2-5. 기술적 지표 (Technical Filter)

**정의:** RSI(14일)와 200일 SMA 위치(가격이 MA200 위/아래)를 결합한 기술적 강도 스코어

**금융공학적 근거:**  
200일 MA는 기관 투자자가 장기 추세를 판단하는 기준선이다. MA200 하회 종목은 기관 매수세 유입이 어렵다. RSI는 과매수/과매도 상태를 0-1로 정규화하여 기술적 모멘텀을 보완.

**계산:**
```
above_ma200 = 1.0 if price > sma_200 else 0.0
rsi_normalized = rsi_14 / 100.0
technical_raw = 0.6 * above_ma200 + 0.4 * rsi_normalized
```

**구현 파일:** `core/factors/technical.py` (신규)

---

## 3. 스코어링 레이어

### 3-1. 백분위 순위화 (Percentile Ranking)

전체 유니버스 내에서 각 팩터를 `scipy.stats.percentileofscore` 또는 `pandas.Series.rank(pct=True)`로 0~1 백분위로 변환.

```
percentile_momentum[i] = rank(momentum_raw[i]) / N  # 높을수록 좋음
percentile_valuation[i] = 1 - rank(valuation_raw[i]) / N  # 낮을수록 좋음 → 역수
```

### 3-2. 동적 가중치 합산

```
weights_input = [w_mom, w_val, w_eps, w_qual, w_tech]  # 사용자 입력
weights_norm = [w / sum(weights_input) for w in weights_input if w > 0]
composite_score = sum(percentile_i * weight_i for ...)
```

합산 전 `w == 0`인 팩터는 완전 배제. 정규화로 합계 1.0 보장.

### 3-3. 하드 필터 (Hard Constraints)

| 토글 | 조건 | 동작 |
|------|------|------|
| 200일 MA 하회 제외 | `above_ma200 == False` | 랭킹 테이블에서 즉시 제거 |
| CFO 음수 제외 | `cfo_positive == False` | 랭킹 테이블에서 즉시 제거 |

프론트엔드에서 필터링 처리 (서버 재요청 없음).

---

## 4. 데이터 레이어

### 4-1. 신규 DB 테이블

```sql
-- 팩터 스코어 캐시 (배치 1회/일 갱신)
CREATE TABLE quant_scores (
  ticker            TEXT,
  universe          TEXT,        -- 'sp500' | 'kospi200'
  as_of             DATE,
  -- 백분위 (0~1, 스코어링용)
  pct_momentum      FLOAT,
  pct_valuation     FLOAT,
  pct_eps_momentum  FLOAT,
  pct_quality       FLOAT,
  pct_technical     FLOAT,
  -- Raw 값 (상세 페이지 카드용)
  raw_momentum      FLOAT,       -- 12-1M 수익률
  raw_fwd_pe        FLOAT,
  raw_pbr           FLOAT,
  raw_psr           FLOAT,
  raw_trailing_pe   FLOAT,
  raw_eps_ttm       FLOAT,
  raw_fwd_eps       FLOAT,
  raw_roe           FLOAT,
  raw_debt_ratio    FLOAT,
  raw_rsi           FLOAT,
  above_ma200       BOOLEAN,
  cfo_positive      BOOLEAN,
  PRIMARY KEY (ticker, universe, as_of)
);

-- 사용자 투자 메모
CREATE TABLE ticker_notes (
  ticker        TEXT PRIMARY KEY,
  opinion       TEXT,            -- '매수검토'|'보유'|'관망'|'매도검토'
  target_price  FLOAT,
  memo          TEXT,
  tags          TEXT,            -- 콤마 구분 문자열
  updated_at    TIMESTAMP
);
```

### 4-2. 기존 코드 재사용

| 기존 파일 | 재사용 방식 |
|-----------|------------|
| `core/data/ohlcv_cache.py` | 모멘텀·기술 팩터 가격 데이터 |
| `core/data/fundamentals_provider.py` | PBR, ROE, CFO, PSR 필드 추가 확장 |
| `core/factors/composite.py` | 백분위 합산 로직 재사용 |
| `core/repository.py` | 신규 테이블 2개 추가 |

---

## 5. 신규 파일 목록

### 백엔드

| 파일 | 역할 |
|------|------|
| `core/data/fundamentals_extended.py` | PBR, PSR, ROE, D/E, CFO 추가 페치 |
| `core/data/universe_provider.py` | S&P 500 티커 목록 관리 (Wikipedia 파싱 or yfinance). KOSPI 200은 Phase 2 — 이번 구현 범위 외. |
| `core/factors/price_momentum.py` | 12-1M 모멘텀 |
| `core/factors/valuation.py` | FWD PER + PBR 통합 밸류 |
| `core/factors/quality.py` | ROE + D/E + CFO |
| `core/factors/technical.py` | RSI(14) + 200일 MA |
| `core/scoring/universe_scorer.py` | 유니버스 배치 계산 → 백분위 → DB upsert |
| `api/routers/screener.py` | `/api/screener/scores`, `/api/screener/ticker/{ticker}`, `/api/screener/refresh`, `/api/screener/notes` |

### 프론트엔드

| 파일 | 역할 |
|------|------|
| `app/screener/page.tsx` | 스크리닝 페이지 (사이드바 + 랭킹 테이블) |
| `app/screener/[ticker]/page.tsx` | 종목 상세 페이지 |
| `components/screener/factor-sidebar.tsx` | 가중치 슬라이더 + 하드필터 토글 (sticky) |
| `components/screener/ranking-table.tsx` | 브라우저 내 재랭킹 테이블, 행 클릭 → 상세 이동 |
| `components/screener/radar-chart.tsx` | 5팩터 레이더 차트 (SVG, recharts 또는 순수 SVG) |
| `components/screener/factor-bars.tsx` | 팩터별 백분위 수평 바 |
| `components/screener/metric-grid.tsx` | 재무 지표 3×3 카드 그리드 (시장 평균 대비 동적 컬러링) |
| `components/screener/note-form.tsx` | 투자 의견 저장 폼 (의견·목표가·메모·태그) |

---

## 6. 페이지 레이아웃 확정

### 화면 A — 종목 스크리닝 (사이드바 레이아웃)

```
┌─────────────────────────────────────────────────────┐
│  Nav: 포트폴리오 | 보유종목 | 백테스트 | [종목분석]    │
├──────────────┬──────────────────────────────────────┤
│  [사이드바]  │  [랭킹 테이블 - 세로 스크롤]          │
│  유니버스    │  # | 티커 | 종합 | 모멘텀 | 밸류 | .. │
│  선택기      │  1   NVDA   0.94   0.98    0.31  ...  │
│              │  2   MSFT   0.89   0.82    0.54  ...  │
│  ─────────── │  (클릭 → /screener/[ticker])          │
│  팩터 슬라이더│                                       │
│  모멘텀 25%  │                                       │
│  밸류    20% │                                       │
│  EPS     20% │                                       │
│  퀄리티  20% │                                       │
│  기술적  15% │                                       │
│  합계 100%   │                                       │
│  ─────────── │                                       │
│  하드 필터   │                                       │
│  ☑ 200MA     │                                       │
│  ☑ CFO       │                                       │
└──────────────┴──────────────────────────────────────┘
```

### 화면 B — 종목 상세 (좌우 분할 + 3×3 그리드)

```
┌─────────────────────────────────────────────────────┐
│  [검색창]  NVDA  NVIDIA Corporation  종합 0.94 / 상위2%│
├────────────────────────────┬────────────────────────┤
│  [레이더 차트] [팩터 바]   │  [투자 의견 기록]      │
│  모멘텀  ████████░ 0.98    │  의견: 매수 검토       │
│  밸류    ███░░░░░░ 0.31    │  목표가: $____         │
│  EPS     ████████░ 0.96    │                        │
│  퀄리티  ████████░ 0.91    │  메모:                 │
│  기술적  ███████░░ 0.88    │  ┌──────────────────┐ │
│                            │  │                  │ │
│  ─────────────────────── │  │  (textarea)      │ │
│  [재무 지표 3×3 그리드]    │  │                  │ │
│  ┌────┬────┬────┐        │  └──────────────────┘ │
│  │PER │FwPE│PBR │        │  태그: _____________   │
│  ├────┼────┼────┤        │  [저장]                │
│  │PSR │EPS │FwEP│        │                        │
│  ├────┼────┼────┤        │                        │
│  │ROE │D/E │RSI │        │                        │
│  └────┴────┴────┘        │                        │
└────────────────────────────┴────────────────────────┘
```

---

## 7. API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/screener/scores?universe=sp500` | 전체 유니버스 백분위 + raw 데이터 반환 |
| GET | `/api/screener/ticker/{ticker}?universe=sp500` | 단일 종목 상세 데이터 |
| POST | `/api/screener/refresh?universe=sp500` | 배치 재계산 트리거 |
| GET | `/api/screener/notes/{ticker}` | 투자 메모 조회 |
| PUT | `/api/screener/notes/{ticker}` | 투자 메모 저장/수정 |

---

## 8. 프론트엔드 상태 관리

```typescript
// 스크리닝 페이지 전역 상태
interface ScreenerState {
  universe: 'sp500' | 'kospi200'
  rawScores: TickerScore[]          // 최초 1회 로드 후 메모리에 보관
  weights: FactorWeights            // 슬라이더 값
  hardFilters: { ma200: boolean; cfo: boolean }
  // 파생 상태 (useMemo)
  filteredRanked: TickerScore[]     // 필터 + 가중치 적용 결과
}

// 가중치 정규화 (합이 0이면 균등 분배)
function normalizeWeights(w: FactorWeights): FactorWeights {
  const total = Object.values(w).reduce((a, b) => a + b, 0)
  if (total === 0) return equalWeights()
  return mapValues(w, v => v / total)
}
```

---

## 9. 재무 지표 카드 동적 컬러링 기준

| 지표 | 좋음 (초록) 조건 | 주의 (빨강) 조건 |
|------|-----------------|-----------------|
| Trailing PER | < S&P500 평균(21x) | > 40x |
| Forward PER | < 18x | > 35x |
| PBR | < 4x | > 10x |
| PSR | < 3x | > 10x |
| EPS YoY | > 0% | < -10% |
| Fwd EPS vs TTM | > +10% | < 0% |
| ROE | > 15% | < 5% |
| D/E Ratio | < 0.5 | > 2.0 |
| RSI | 40–70 (건전 추세) | ≥ 70 (과열) 또는 ≤ 30 (과매도) |

---

## 10. 데이터 흐름 요약

```
[배치 - 1일 1회]
universe_provider (S&P 500 티커 목록)
  → 각 팩터 병렬 계산 (ThreadPool, max_workers=20)
    → price_momentum: OHLCV 캐시에서 월말 종가
    → valuation: fundamentals_extended (fwd_pe, pbr, psr)
    → eps_momentum: fundamentals DB 이력 (1M, 3M 전 비교)
    → quality: roe, debt_ratio, operating_cashflow
    → technical: OHLCV에서 RSI(14), SMA(200) 계산
  → 각 팩터 전체 유니버스 기준 percentile_rank
  → DuckDB quant_scores upsert

[스크리닝 페이지 로드]
GET /api/screener/scores?universe=sp500
  → ~500개 × (5 백분위 + 9 raw값 + 2 boolean) JSON (~35KB)
  → React state에 저장

[슬라이더 조작 (0ms)]
  weights 변경 → useMemo 재계산
    → hard filter 적용 → weighted sum → sort desc → top 50 렌더

[종목 클릭]
  router.push('/screener/NVDA')
  → GET /api/screener/ticker/NVDA (상세 raw + 비교 데이터)
  → 레이더 차트 + 팩터 바 + 지표 카드 렌더
  → GET /api/screener/notes/NVDA (저장된 메모)
```

---

## 11. 의존성 추가 필요

- `pandas_datareader` 또는 `requests` (S&P 500 티커 목록 파싱)
- `scipy` — Winsorizing (`scipy.stats.mstats.winsorize`) 및 백분위 계산
- 프론트엔드 레이더 차트: 순수 SVG 직접 구현 (외부 차트 라이브러리 불필요, 기존 패턴 유지)

---

## 12. 아키텍처 보정 사항 (퀀트 매니저 피드백)

### 12-1. 밸류에이션 아웃라이어 왜곡 방지 (`core/factors/valuation.py`)

**문제:** S&P 500에는 Forward PER 수백~수천 배 극단 아웃라이어가 존재한다. 단순 Z-score 적용 시 평균·표준편차가 왜곡되어 정상 종목들의 변동성이 뭉개진다.

**해결 — Winsorizing + Rank-based Fallback:**

```python
# Step 1: 윈저라이징 — 하위 1%, 상위 99%로 강제 클리핑
from scipy.stats.mstats import winsorize
winsorized_pe = winsorize(raw_fwd_pe_series, limits=[0.01, 0.01])

# Step 2: 윈저라이징된 값으로 Z-score 계산
z_fwd_pe = (winsorized_pe - winsorized_pe.mean()) / winsorized_pe.std()

# Fallback: 아웃라이어가 극심해 std ≈ 0 이면 rank 기반 표준화로 전환
if winsorized_pe.std() < 1e-6:
    z_fwd_pe = winsorized_pe.rank(pct=True) * 2 - 1  # [-1, 1] 범위
```

적용 대상: `raw_fwd_pe`, `raw_pbr` 모두 동일 처리.

---

### 12-2. DB 조회 성능 최적화 (`core/repository.py`)

**문제:** `quant_scores`는 날짜 누적 시계열 테이블. 단순 `SELECT * WHERE universe=?` 시 수년치 스캔.

**해결 — Composite Index + 최신 날짜 서브쿼리:**

```sql
-- 마이그레이션 시 1회 실행
CREATE INDEX IF NOT EXISTS idx_quant_scores_universe_date
ON quant_scores (universe, as_of);

-- 조회 쿼리: MAX(as_of) 서브쿼리로 최신 배치만 정확히 인덱싱
SELECT * FROM quant_scores
WHERE universe = ? AND as_of = (
    SELECT MAX(as_of) FROM quant_scores WHERE universe = ?
);
```

`_init_schema()`에 인덱스 생성 DDL 포함. 최초 1회만 실행되므로 부담 없음.

---

### 12-3. RSI 정규화 보정 및 프론트엔드 컬러링 기준 수정

**문제:** `rsi / 100.0`은 단순 스케일 변환. 모멘텀이 강하게 분출하는 RSI 60~70 종목이 RSI 50 중립 종목보다 낮은 점수를 받는 역설 발생.

**백엔드 수정 (`core/factors/technical.py`):**

```python
# RSI를 유니버스 내 백분위 순위로 가공 — 상대적 모멘텀 강도 반영
rsi_percentile = pd.Series(rsi_values).rank(pct=True)  # 0~1
technical_raw = 0.6 * above_ma200 + 0.4 * rsi_percentile
```

**프론트엔드 컬러링 기준 수정 (`components/screener/metric-grid.tsx`):**

| RSI 구간 | 컬러 | 의미 |
|----------|------|------|
| 40 이상 70 미만 | 초록 | 건전한 상승 추세 (장기 정배열 구간) |
| 30 이하 | 빨강 | 극단적 과매도 |
| 70 이상 | 빨강 | 과열 권역 |
| 30~40 | 노랑 | 약세 경계 |

```typescript
// metric-grid.tsx 컬러링 함수
function rsiColor(rsi: number): 'green' | 'yellow' | 'red' {
  if (rsi >= 40 && rsi < 70) return 'green'   // 건전 추세
  if (rsi >= 30 && rsi < 40) return 'yellow'  // 경계
  return 'red'                                 // 과열(≥70) 또는 과매도(≤30)
}
```

**설계 문서 섹션 9 컬러링 기준 수정:**  
RSI 항목을 `40–70 → 초록 / 70 이상·30 이하 → 빨강 / 30–40 → 노랑`으로 교체.
