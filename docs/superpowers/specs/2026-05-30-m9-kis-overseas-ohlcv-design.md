# M9: KIS 해외 OHLCV 연동 설계

**날짜:** 2026-05-30  
**범위:** 미장(NASDAQ/NYSE/AMEX) 일봉 OHLCV 소스를 yfinance bulk → KIS API 우선으로 전환

---

## 1. 목표

현재 해외 종목 일봉 데이터는 `yfinance.download()` bulk 호출로 가져온다. Yahoo Finance는 IP 차단·rate limit 위험이 있어 불안정하다. KIS Open API의 해외 일봉 엔드포인트를 1차 소스로 사용하고, KIS 실패 시 yfinance를 fallback으로 유지한다.

**완료 조건:**
- `AAPL`, `SPY`, `QQQ` 캔들이 KIS에서 정상 수신됨 (`/api/candles?ticker=AAPL&period=3M`)
- KIS 실패 시 yfinance fallback 동작 확인
- 신규 테스트 6개 통과

---

## 2. 변경 범위

변경 파일 3개만 수정한다.

| 파일 | 변경 |
|------|------|
| `core/prices/kis.py` | `fetch_ohlcv_overseas()` 함수 추가 |
| `core/data/ohlcv_cache.py` | `_fetch_and_store()` US 분기 추가 |
| `tests/test_kis_ohlcv.py` | 신규 단위 테스트 6개 |

---

## 3. KIS 해외 일봉 API 스펙

**엔드포인트:** `GET /uapi/overseas-price/v1/quotations/dailyprice`  
**tr_id:** `HHDFS76240000`

### 요청 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `AUTH` | `""` | 항상 빈 문자열 |
| `EXCD` | `NAS` / `NYS` / `AMS` | 거래소 코드 |
| `SYMB` | `AAPL` 등 | 종목 심볼 |
| `GUBN` | `"0"` | 0=일봉 |
| `BYMD` | `YYYYMMDD` | 이 날짜까지의 데이터 반환 |
| `MODP` | `"1"` | 수정주가 적용 |
| `KEYB` | `""` | 페이지네이션 키 (첫 요청은 빈 문자열) |

### 응답 구조

```json
{
  "rt_cd": "0",
  "output1": { "keyb": "다음페이지키_or_빈문자열" },
  "output2": [
    {
      "xymd": "20250530",
      "open": "150.1",
      "high": "152.3",
      "low":  "149.8",
      "clos": "151.5",
      "tvol": "12345678"
    }
  ]
}
```

- `output2`는 최신→과거 순 정렬, 한 페이지 최대 100행
- `output1.keyb` 빈 문자열이면 마지막 페이지

---

## 4. 구현 상세

### 4-1. `fetch_ohlcv_overseas()` (`core/prices/kis.py`)

```python
def fetch_ohlcv_overseas(
    ticker: str,
    start: date,
    end: date,
    market: str | None = None,
) -> pd.DataFrame:
```

- **EXCD 결정:** `market` 파라미터 → `_MARKET_TO_EXCD` 변환. None이면 `NAS→NYS→AMS` 순서 시도
- **페이지네이션:** `BYMD=end`, `KEYB=""` 첫 요청 → `output1.keyb`로 다음 페이지. 최대 5페이지(500일) 제한
- **start 필터링:** `output2`에서 `xymd < start` 행 제외
- **반환:** `DatetimeIndex` DataFrame, columns: `Open High Low Close Volume`
- **실패 시 빈 DataFrame 반환** (예외 전파하지 않음)

**EXCD 순서 로직:**
```
market=NASDAQ → EXCD=[NAS]          (단일 거래소만 시도)
market=None   → EXCD=[NAS, NYS, AMS] (순차 시도, 유효 데이터 첫 성공)
```

### 4-2. `_fetch_and_store()` 수정 (`core/data/ohlcv_cache.py`)

현재 구조:
```
domestic_tickers → KIS/FDR
overseas_tickers → yfinance bulk
```

변경 후:
```
domestic_tickers    → KIS/FDR (변경 없음)
overseas_tickers
  ├─ [KIS 시도] fetch_ohlcv_overseas() 개별 호출
  │    성공 → store, 다음 ticker
  │    빈 DataFrame → kis_failed 목록에 추가
  └─ [yfinance fallback] kis_failed → yfinance bulk → 개별 재시도
```

**US 판별:** 별도 분류 없음. 모든 해외 ticker를 KIS에 시도. 일본(`.T`), 홍콩(`.HK`) 등은 NAS/NYS/AMS 모두 실패 → 자연스럽게 yfinance fallback.

---

## 5. 에러 처리

| 상황 | 처리 |
|------|------|
| KIS 토큰 없음 | 빈 DataFrame → yfinance fallback |
| `rt_cd != "0"` | 다음 EXCD 시도, 모두 실패 시 빈 DataFrame |
| `clos == "0"` or 빈 값 | 해당 row 스킵 |
| 네트워크 타임아웃 | 빈 DataFrame → yfinance fallback |
| 페이지 5회 초과 | 수집된 데이터까지만 반환 |

---

## 6. 테스트

**파일:** `tests/test_kis_ohlcv.py`

| 테스트 | 검증 |
|--------|------|
| `test_fetch_ohlcv_overseas_success` | 정상 100행 응답 → DataFrame shape/columns |
| `test_fetch_ohlcv_overseas_pagination` | 2페이지(keyb 있음→없음) → 행 합산 |
| `test_fetch_ohlcv_overseas_empty_response` | `output2=[]` → 빈 DataFrame |
| `test_fetch_ohlcv_overseas_no_token` | `KIS_APPKEY` 없음 → 빈 DataFrame |
| `test_ohlcv_cache_uses_kis_for_overseas` | `fetch_ohlcv_overseas` mock → KIS 경로 호출 확인 |
| `test_ohlcv_cache_fallback_to_yfinance` | KIS 빈 DataFrame → yfinance bulk 호출 확인 |

모두 `unittest.mock.patch`로 외부 HTTP 호출 차단. 실제 API 호출 없음.

---

## 7. 제외 범위 (YAGNI)

- 일본/홍콩/중국 시장 KIS 연동 — 미장만 현실적으로 안정적
- KIS 해외 종목명 캐시 보완 — 기존 `_get_name()` 그대로 사용
- 주문 실행 / 계좌 잔고 조회 — 별도 마일스톤
- WebSocket 실시간 시세 — 별도 마일스톤
