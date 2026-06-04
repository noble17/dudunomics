# Finviz Bulk 전환 + 종목 상세 차트 설계

**날짜:** 2026-06-01  
**상태:** 설계 승인 완료, 구현 대기

---

## 배경 & 동기

- FMP 무료 250 calls/일 → sp500 배치(503종목 × 2 calls = 1,006회) 수집 불가
- Finviz 스크리너 bulk: sp500 전체를 ~20 requests로 가져올 수 있음
- 종목 상세 페이지에 성장성 차트(EPS/매출/ROE)와 기술적 차트(EMA/주가&EPS) 추가 필요

---

## Feature A — Finviz 스크리너 Bulk 전환

### 현황
- `_sync_quarterly()`: FMP API 티커별 개별 호출 → 배치마다 1,006 calls (무료 한도 초과)
- `raw_eps_momentum`: quarterly_financials에서 YoY 계산

### 변경
- FMP quarterly sync **완전 제거**
- Finviz 스크리너 bulk fetch (~20 requests for sp500, ~5 for nasdaq100):
  - `EPS Q/Q` → `raw_eps_momentum` 직접 사용 (계산 방식 동일: 전년 동기 YoY)
  - `ROE`, `Debt/Eq` → quality factor 보완
- `quarterly_financials` DB: Feature B/C 차트 히스토리용으로 유지 (단, sync 로직 제거)

### Finviz 스크리너 URL 패턴
```
https://finviz.com/screener.ashx?v=152&f=idx_sp500&o=ticker&r=1
```
- `v=152`: custom view (EPS Q/Q 등 포함)
- `r=1`, `r=21`, `r=41` ... 25개씩 페이지네이션
- 컬럼: Ticker, EPS Q/Q, EPS Y/Y TTM, ROE, Debt/Eq, Market Cap

### 기존 버그 수정 (이미 완료)
- `repository.py:1233` — `get_quarterly_bulk` ORDER BY 누락 → `ORDER BY ticker, period DESC` 추가 완료

---

## Feature B — 성장성/수익성 차트

### UI (종목 상세 페이지 `/screener/[ticker]`)

**섹션 제목:** "성장성과 수익성 흐름은?"

**탭 3개:**
- 매출액 (Revenue, 단위: 백만달러)
- EPS 주당순이익 (단위: 달러)
- ROE (단위: %)

**각 탭 구성:**
- 연간 바 차트: 파란 막대(실적) + 회색 막대(예상)
- 막대 위 레이블 표시
- X축: YYYY.MM 형식 (회계연도 종료월)
- 우상단: "최근실적발표 YY.MM.DD · 단위: XXX"
- 좌상단: "연간" 뱃지

**하단 고정 메트릭 (탭 공통):**
```
시가총액          375,920 백만달러
PER   415.80배   PER(F)  289.59배
PEG     9.54배   PSR      76.40배
```

### 데이터 소스: stockanalysis.com `/stocks/{ticker}/forecast/`
**검증 완료 (AAPL 기준):**
- Revenue: 과거 5년 + FY2026, FY2027 예상 ✅
- EPS: 과거 5년 + FY2026, FY2027 예상 ✅
- ROE: 직접 컬럼 없음 → balance sheet에서 `Net Income / Shareholders' Equity × 100` 계산
- FY2028~: Pro(유료) 벽 → 2개년 예상만 사용

**메트릭:** 기존 Finviz 스냅샷 활용 (이미 있음)
- `market_cap_m`, `trailing_pe`, `forward_pe`, `peg`, `price_to_sales`

### 백엔드 신규 엔드포인트
```
GET /api/screener/ticker/{ticker}/financials
Response:
{
  "revenue":   [{"year": "2024", "period_end": "2024.09", "value": 391035, "is_estimate": false}, ...],
  "eps":       [{"year": "2024", "period_end": "2024.09", "value": 6.09, "is_estimate": false}, ...],
  "roe":       [{"year": "2024", "period_end": "2024.09", "value": 14.7, "is_estimate": false}, ...],
  "latest_report_date": "2026.05.26",
  "metrics": {
    "market_cap_m": 375920,
    "trailing_pe": 415.8,
    "forward_pe": 289.59,
    "peg": 9.54,
    "price_to_sales": 76.4
  }
}
```

### 캐시 전략
- SQLite 캐시 24h TTL (기존 fundamentals_cache.sqlite 패턴 따름)

---

## Feature C — 주가 흐름 차트

### UI

**섹션 제목:** "주가 흐름은?"

**탭 2개:**

#### Tab 1 — 지수이동평균선(EMA)
- 단기/중기 토글: 단기=3개월, 중기=1년(전체 ohlcv 기간)
- EMA5 (초록) / EMA20 (회색) / EMA60 (파랑) 라인
- X축: YY.MM 형식

#### Tab 2 — 주가&EPS
- 이중 축 차트
  - 좌축 + 파란 라인: 일봉 주가
  - 우축 + 초록 계단형: 분기 EPS (실적 발표 시점 기준)
- 예상 구간: 점선 박스로 표시
- X축: YYYY.MM 형식 (다년간)
- 범례: "● 주가  ● 주당순이익"

### 데이터 소스
- **주가**: `ohlcv_cache` (380일치 보유)
- **EMA 계산**: `pandas.Series.ewm(span=n, adjust=False).mean()`
- **분기 EPS**: `quarterly_financials` DB (period별 EPS)
- **EPS 예상**: stockanalysis.com forecast (Feature B에서 재사용)

### 백엔드 신규 엔드포인트
```
GET /api/screener/ticker/{ticker}/price-chart
Response:
{
  "ohlcv": [{"date": "2025-06-01", "close": 210.5}, ...],
  "ema": {
    "e5":  [{"date": "2025-06-01", "value": 211.2}, ...],
    "e20": [...],
    "e60": [...]
  },
  "quarterly_eps": [
    {"period": "2025Q1", "date": "2025-03-31", "eps": 1.57, "is_estimate": false},
    ...
  ]
}
```

---

## 파일 변경 계획

### 신규 파일
- `core/data/stockanalysis_financials.py` — 연간 재무 + 예상 스크래퍼
- `core/data/finviz_screener.py` — bulk 스크리너 (EPS Q/Q, ROE, Debt/Eq)
- `api/routers/stock_detail.py` — `/financials`, `/price-chart` 엔드포인트
- `frontend/components/screener/growth-chart.tsx` — 성장성 바 차트
- `frontend/components/screener/price-chart.tsx` — EMA + 주가&EPS 차트

### 수정 파일
- `core/scoring/universe_scorer.py` — FMP quarterly 제거, Finviz bulk 연동
- `api/main.py` — 신규 라우터 등록
- `frontend/app/screener/[ticker]/page.tsx` — 두 섹션 추가

### 제거 대상
- `_sync_quarterly()` in `universe_scorer.py` (FMP quarterly sync 로직)
- FMP quarterly 의존성 (`fmp_quarterly.py`는 보존, 호출만 제거)

---

## 미결 사항
- Finviz 스크리너 bulk: custom view 파라미터 확인 필요 (EPS Q/Q 컬럼 포함 여부)
- 국내 종목 (KS/KQ): stockanalysis.com 미지원 → 히스토리 차트 한국 종목 처리 방법
  - 옵션: naver_quarterly 집계로 대체 or "데이터 없음" 표시
