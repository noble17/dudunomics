# OHLCV DuckDB Cache Layer — Design Spec

**Date:** 2026-05-27  
**Status:** Approved

## 목표

백테스트 실행 시 매번 yfinance에서 OHLCV 데이터를 다운로드하는 구조를 개선한다.
과거 데이터는 불변이므로 한 번 받은 데이터는 DuckDB에 캐시하고 이후 요청은 DB에서 직접 읽는다.

## 범위

- 주가 OHLCV (`prices_provider.py`)
- 시장 지수 OHLCV — SPY, ^KS11 (`index_provider.py`)
- 캐시 저장소: 기존 `prices_cache` 테이블 (이미 `repository.py` 스키마에 존재)

## 아키텍처

### 파일 변경 목록

| 파일 | 변경 | 내용 |
|------|------|------|
| `core/data/ohlcv_cache.py` | 신규 | 캐시 로직 전담 모듈 |
| `core/repository.py` | 수정 | DB read/write 함수 2개 추가 |
| `core/data/prices_provider.py` | 수정 | yf.download() → ohlcv_cache.fetch_ohlcv() |
| `core/data/index_provider.py` | 수정 | yf.download() → ohlcv_cache.fetch_index() |

기존 호출부(백테스트 엔진 등)는 수정 없음 — 반환 타입 시그니처 그대로 유지.

### 데이터 흐름

```
백테스트 요청
    ↓
prices_provider.fetch_ohlcv(tickers, start, end)
    ↓
ohlcv_cache.fetch_ohlcv(tickers, start, end)
    ├── 완전 히트: prices_cache에서 읽기
    ├── 부분 히트: 누락 구간만 yfinance fetch → upsert → DB 읽기
    └── 캐시 없음: 전체 구간 yfinance fetch → upsert → DB 읽기
```

## DB 스키마

기존 테이블 그대로 사용 (변경 없음):

```sql
CREATE TABLE IF NOT EXISTS prices_cache (
    ticker TEXT,
    date   DATE,
    open   DOUBLE,
    high   DOUBLE,
    low    DOUBLE,
    close  DOUBLE,
    volume BIGINT,
    PRIMARY KEY (ticker, date)
);
```

인덱스(SPY, ^KS11)도 동일 테이블에 티커명 그대로 저장.

## 캐시 히트 판정

티커별 `min(date)`, `max(date)` 조회 후 판정:

| 상황 | 조건 | 동작 |
|------|------|------|
| 완전 히트 | `min_date <= start` AND `max_date >= end` | DB에서 읽기 |
| 그 외 | 위 조건 불만족 (앞/뒤/전체 누락 모두 포함) | 전체 구간 yfinance fetch → upsert → DB 읽기 |

`ON CONFLICT DO NOTHING` 적용으로 중복 upsert 자동 무시.
앞부분 누락(`min_date > start`)과 뒷부분 누락(`max_date < end`) 케이스를 별도 처리하지 않고 전체 재fetch로 통일한다. 과거 데이터는 불변이라 중복 fetch 비용만 있을 뿐 정합성 문제는 없다.

## 공개 인터페이스

```python
# core/data/ohlcv_cache.py

def fetch_ohlcv(
    tickers: list[str],
    start: date,
    end: date,
) -> tuple[pd.DataFrame, list[str]]:
    """MultiIndex(ticker, field) DataFrame + warnings 반환."""

def fetch_index(
    symbol: str,   # "SPY" | "^KS11"
    start: date,
    end: date,
) -> pd.Series:
    """종가 시계열(tz-naive) 반환."""
```

```python
# core/repository.py 추가 함수

def get_ohlcv_range(ticker: str) -> tuple[date, date] | None:
    """캐시된 (min_date, max_date) 반환. 없으면 None."""

def upsert_ohlcv_rows(rows: list[dict]) -> None:
    """(ticker, date, open, high, low, close, volume) 배치 insert. 중복 무시."""
```

## 에러 처리

- **yfinance 실패:** 경고를 `warns` 리스트에 추가, 해당 티커 건너뜀 (기존 동작 유지)
- **DB 읽기 실패:** 로그 경고 후 yfinance 직접 호출 폴백
- **`end=today`:** yfinance가 어차피 어제까지만 반환 (exclusive). 별도 처리 없음. 다음날 재실행 시 자동으로 채워짐

## 미포함 항목

- PBR / 시계열 PER 그래프 (별도 태스크)
- 종목 상세 페이지 프론트엔드 (별도 태스크)
- KIS API로 소스 교체 (선택적 향후 작업)
