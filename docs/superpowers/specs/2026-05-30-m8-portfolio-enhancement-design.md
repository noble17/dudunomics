# M8 포트폴리오 고도화 설계

**날짜:** 2026-05-30  
**브랜치:** feat/nextjs-fastapi-migration  
**상태:** 승인됨

---

## 개요

Bloomberg Terminal에 포트폴리오 고도화 기능 4종을 추가한다:

- **A) 매매 내역 추적** — trades-first 아키텍처로 보유 현황 자동 계산
- **B) 성과 분석** — Sharpe ratio, MDD, KOSPI/S&P500 벤치마크 대비 수익률
- **C) Terminal 통합** — PORTFOLIO 탭 신설 (레이아웃 C: 왼쪽 사이드바)
- **D) 리밸런싱 제안** — 목표 비중 vs 현재 비중, 필요 거래 금액 자동 계산

---

## 1. 데이터 아키텍처

### 신규 테이블: `trades`

```sql
CREATE TABLE trades (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES users(id),
  ticker      TEXT    NOT NULL,
  market      TEXT,                    -- KR / US
  trade_type  TEXT    NOT NULL,        -- BUY / SELL
  quantity    REAL    NOT NULL,
  price       REAL    NOT NULL,        -- 거래 단가
  currency    TEXT    NOT NULL,        -- KRW / USD
  traded_at   TEXT    NOT NULL,        -- ISO8601 날짜 (YYYY-MM-DD)
  fee         REAL    DEFAULT 0,
  note        TEXT,
  created_at  TEXT    DEFAULT (datetime('now'))
);
```

### 기존 테이블 변경

`holdings`에 `target_weight` 컬럼 추가 (DB migration):

```sql
ALTER TABLE holdings ADD COLUMN target_weight REAL DEFAULT NULL;
```

### 마이그레이션 전략

기존 더미 holdings → `trades` 시딩:

- 기존 `holdings` 레코드를 `traded_at='2024-01-01'`의 BUY 거래로 변환
- `_run_migrations()` 내에 마이그레이션 스텝 추가
- 이후 `avg_price`/`quantity`는 trades 합산으로 자동 계산

### 파생 계산

- **avg_price** = `SUM(qty * price WHERE BUY) / SUM(qty WHERE BUY)` (단순 평균 단가)
- **current_quantity** = `SUM(qty WHERE BUY) - SUM(qty WHERE SELL)`
- **realized_pnl** = SELL 시 `(sell_price - avg_price_at_sell) * qty`
- **unrealized_pnl** = `(current_price - avg_price) * current_quantity`

---

## 2. API 설계

### 신규 엔드포인트

#### Trades (`/api/trades`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/trades` | 거래 내역 목록 (최신순, `?ticker=` 필터 지원) |
| POST | `/api/trades` | 거래 등록 (BUY/SELL) |
| DELETE | `/api/trades/{id}` | 거래 삭제 |

POST body:
```json
{
  "ticker": "AAPL",
  "market": "US",
  "trade_type": "BUY",
  "quantity": 10,
  "price": 184.2,
  "currency": "USD",
  "traded_at": "2025-01-15",
  "fee": 0,
  "note": ""
}
```

#### Performance (`/api/portfolio/performance`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/portfolio/performance` | 성과 지표 + 벤치마크 |

Query params: `period=1m|3m|6m|1y|all` (default: `6m`)

Response:
```json
{
  "sharpe": 1.42,
  "mdd": -8.3,
  "total_return": 14.2,
  "annualized_return": 22.1,
  "benchmark": {
    "kospi":  { "return": 10.0, "correlation": 0.62 },
    "sp500":  { "return": 13.1, "correlation": 0.71 }
  },
  "chart": [
    { "date": "2025-01-01", "portfolio": 0.0, "kospi": 0.0, "sp500": 0.0 }
  ]
}
```

벤치마크 데이터는 `yfinance`로 `^KS11`(KOSPI), `^GSPC`(S&P500) 조회.  
yfinance 실패 시 벤치마크 없이 포트폴리오 지표만 반환 (graceful fallback).

#### Rebalancing (`/api/portfolio/rebalancing`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/portfolio/rebalancing` | 현재/목표 비중 비교 + 필요 거래 금액 |
| PATCH | `/api/holdings/{ticker}` | 목표 비중 업데이트 |

GET Response:
```json
[{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "current_weight": 30.0,
  "target_weight": 25.0,
  "diff_weight": -5.0,
  "action": "SELL",
  "amount_krw": 3200000
}]
```

PATCH body: `{ "target_weight": 25.0 }`  
Soft validation: target_weight 합계가 100% 초과 시 응답에 경고 포함 (거부하지 않음).

### 기존 엔드포인트 변경

`GET /api/portfolio/current` 응답에 필드 추가:
- `unrealized_pnl_krw: float`
- `realized_pnl_krw: float`

---

## 3. 프론트엔드 컴포넌트

### 레이아웃 C — 왼쪽 사이드바

```
┌─────────────────────────────────────────────────────┐
│  MARKETS │ TERMINAL │ PORTFOLIO ◀ │ SCREENER        │
├──────────────┬──────────────────────────────────────┤
│              │                                      │
│  POSITIONS   │  PERFORMANCE CHART                   │
│  (보유 현황)  │  (포트폴리오 vs KOSPI vs S&P500)      │
│              │  Sharpe / MDD / YTD / vs벤치마크     │
│              ├──────────────────────────────────────┤
│──────────────│                                      │
│  REBALANCING │  TRADE LOG                           │
│  (리밸런싱)   │  (거래 내역 + 거래 추가 버튼)          │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

### 신규 컴포넌트 파일

| 파일 | 역할 |
|------|------|
| `frontend/components/terminal/tabs/PortfolioTab.tsx` | PORTFOLIO 탭 최상위, 레이아웃 C 그리드 |
| `frontend/components/terminal/widgets/PositionsPanel.tsx` | 왼쪽 상단 — 보유 종목 목록, 미실현 손익 |
| `frontend/components/terminal/widgets/RebalancingPanel.tsx` | 왼쪽 하단 — 현재/목표 비중, BUY/SELL 금액 |
| `frontend/components/terminal/widgets/PerformancePanel.tsx` | 오른쪽 상단 — 수익률 차트(lightweight-charts), 지표 |
| `frontend/components/terminal/widgets/TradeLogPanel.tsx` | 오른쪽 하단 — 거래 테이블, 거래 추가 버튼 |
| `frontend/components/terminal/widgets/AddTradeModal.tsx` | 거래 등록 폼 모달 |

### 기존 파일 변경

- `frontend/components/terminal/WidgetRegistry.ts` — `portfolio` 키 등록
- `frontend/components/terminal/TabShell.tsx` — PORTFOLIO 탭 추가
- `frontend/lib/api.ts` — trades API, performance API, rebalancing API 추가
- `frontend/lib/types.ts` — Trade, PerformanceData, RebalancingRow 타입 추가

### 인터랙션

- PositionsPanel 종목 클릭 → TradeLogPanel이 해당 ticker로 필터링
- RebalancingPanel에서 목표 비중 인라인 편집 (PATCH 호출)
- PerformancePanel 기간 버튼 (1M/3M/6M/1Y/ALL) 클릭 시 차트 갱신

---

## 4. 테스트 전략

### 신규 테스트 파일 (총 19개)

**`tests/test_trades_api.py`** (8개)
- POST BUY/SELL 등록 정상 동작
- GET 목록 조회, ticker 필터
- DELETE 거래 삭제
- BUY 후 holdings avg_price/quantity 자동 갱신
- SELL 후 realized_pnl 계산
- 수량 초과 SELL 시 422 반환

**`tests/test_performance_api.py`** (6개)
- 응답 스키마 검증
- Sharpe ratio 계산 정확성 (고정 스냅샷 데이터)
- MDD 계산 정확성
- yfinance 실패 시 graceful fallback
- period 파라미터 필터링

**`tests/test_rebalancing_api.py`** (5개)
- GET 정상 응답
- current_weight 계산 정확성
- action(BUY/SELL/HOLD) 로직
- PATCH target_weight 업데이트
- 합계 100% 초과 시 경고 포함 응답

### 범위 외

기존 pre-existing 실패 20개 (test_holdings_api, test_portfolio_api 등)는 M8 범위 아님.

---

## 5. 구현 순서

1. DB — `trades` 테이블 + `target_weight` 컬럼 + migration
2. Backend — trades CRUD + holdings 자동 갱신 로직
3. Backend — performance 계산 (Sharpe, MDD, benchmark)
4. Backend — rebalancing 계산
5. Frontend — 타입/API 클라이언트
6. Frontend — PortfolioTab + 4개 패널 컴포넌트
7. Frontend — Terminal 탭 등록
8. Tests — 19개 테스트
