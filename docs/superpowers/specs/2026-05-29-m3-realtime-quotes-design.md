# M3 실시간 시세 연결 설계

**날짜:** 2026-05-29  
**브랜치:** feat/nextjs-fastapi-migration  
**범위:** IndexStrip에 SPY / QQQ / USD/KRW / BTC 실시간 시세 연결

---

## 1. 목표

터미널 상단 IndexStrip의 "M3에서 실시간 연결" 플레이스홀더를 실제 시세 데이터로 교체한다. 10초 REST 폴링으로 가격 + 등락폭 + 등락률을 표시한다.

## 2. 결정 사항

| 항목 | 결정 | 근거 |
|---|---|---|
| 갱신 방식 | 10초 REST 폴링 | SSE는 백엔드도 결국 KIS/yfinance를 폴링해야 함 — 구조적 차이 없음 |
| BTC 소스 | Upbit 공개 REST API | API 키 불필요, KRW 기준 거래소 실가, `signed_change_rate` 필드 포함 |
| 표시 형식 | 가격 + 등락폭 + 등락률 | Bloomberg 터미널 컨텍스트에 맞는 최대 정보량 |
| 엔드포인트 | 단일 `/api/quotes` 배치 | 프론트 요청 1회, 백엔드 오류 처리 단일 지점 |

## 3. 아키텍처

```
[IndexStrip] —— 10초 setInterval ——→ GET /api/quotes (JWT 쿠키)
                                          │
                        ┌─────────────────┼──────────────────┐
                        ▼                 ▼                  ▼
                  KIS/yfinance     기존 KisFxProvider    Upbit 공개 API
                 (SPY, QQQ)         (USD/KRW)         (BTC/KRW)
```

## 4. 백엔드

### 4-1. `core/prices/upbit.py` (신규)

```python
class UpbitProvider:
    BASE = "https://api.upbit.com/v1"

    def get_btc_krw(self) -> Price:
        """GET /v1/ticker?markets=KRW-BTC → Price(BTC, KRW)"""
        # trade_price         → current
        # signed_change_price → change_abs
        # signed_change_rate * 100 → change_pct
```

- API 키 불필요 (공개 엔드포인트)
- 타임아웃 10초, 실패 시 RuntimeError

### 4-2. `api/models.py` 추가

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

### 4-3. `api/routers/quotes.py` (신규)

```
GET /api/quotes  — JWT 인증 필요
```

응답 예시:
```json
{
  "SPY":    { "price": 597.42,    "change_abs": 7.24,      "change_pct": 1.23  },
  "QQQ":    { "price": 519.87,    "change_abs": -2.36,     "change_pct": -0.45 },
  "USDKRW": { "price": 1372.5,    "change_abs": 0.0,       "change_pct": 0.00  },
  "BTC":    { "price": 151234000, "change_abs": 4237000,   "change_pct": 2.87  }
}
```

**데이터 소스 매핑:**
- SPY, QQQ: 기존 `KisProvider.get_current_prices()` 재사용. `change_abs = price * change_pct / 100`으로 계산
- USD/KRW: 기존 `KisFxProvider.get_rate("USDKRW")` 재사용. `change_abs = 0`, `change_pct = 0` 고정
- BTC: 신규 `UpbitProvider.get_btc_krw()`

**오류 처리:** 개별 심볼 조회 실패 시 해당 심볼만 `null` 반환 (나머지 정상 반환). 전체 실패 시 503.

### 4-4. `main.py` 라우터 등록

기존 라우터 등록 패턴에 맞춰 `quotes.router` 추가.

## 5. 프론트엔드

### 5-1. `frontend/lib/types.ts` 추가

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

### 5-2. `frontend/lib/api.ts` 추가

```typescript
export async function fetchQuotes(): Promise<QuotesOut>
```

### 5-3. `frontend/hooks/useQuotes.ts` (신규)

```typescript
export function useQuotes(): QuotesOut | null
// - 10초 setInterval 폴링
// - 초기값: null (로딩 중 → "—" 표시)
// - 오류 시: 이전 성공값 유지 (깜빡임 방지)
// - 언마운트 시 clearInterval
```

### 5-4. `frontend/components/terminal/IndexStrip.tsx` 업데이트

**표시 형식:**
```
SPY  597.42  ▲+7.24 (+1.23%)    QQQ  519.87  ▼-2.36 (-0.45%)
USD/KRW  1,372.5  +0.0    BTC  151,234,000  ▲+4,237,000 (+2.87%)
```

**숫자 포맷:**
- SPY / QQQ: 소수점 2자리
- USD/KRW: 소수점 1자리, 천 단위 콤마
- BTC: 정수, 천 단위 콤마 (원화 KRW)

**색상 (Upbit KR 컨벤션):**
- 상승: `--color-gain` (빨강, `#DD3C44`)
- 하락: `--color-loss` (파랑, `#1375EC`)
- 보합: `--color-text-secondary`

**로딩 / 오류 상태:**
- 초기 로딩: `—` 유지
- 오류 발생: 마지막 성공값 유지

## 6. 변경 파일 목록

| 파일 | 변경 |
|---|---|
| `core/prices/upbit.py` | 신규 |
| `api/routers/quotes.py` | 신규 |
| `api/models.py` | `QuoteItem`, `QuotesOut` 추가 |
| `api/main.py` | quotes 라우터 등록 |
| `frontend/lib/types.ts` | `QuoteItem`, `QuotesOut` 추가 |
| `frontend/lib/api.ts` | `fetchQuotes` 추가 |
| `frontend/hooks/useQuotes.ts` | 신규 |
| `frontend/components/terminal/IndexStrip.tsx` | 실제 데이터 연결 |

## 7. 테스트

- `tests/test_quotes_api.py`: `/api/quotes` 응답 구조 검증, 각 심볼 필드 존재 확인
- BTC 브라우저 검증: IndexStrip에 실제 가격 + 등락률 표시 확인
