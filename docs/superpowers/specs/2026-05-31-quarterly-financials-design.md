# Quarterly Financials — Design Spec
Date: 2026-05-31

## 목표

국내(KS/KQ) 및 미국(SP500) 종목의 분기별 재무 데이터를 영구 저장하고,
Quality 팩터(ROE/부채비율) 및 EPS 모멘텀(YoY) 계산에 활용한다.

## 배경

- 현재 국내 종목은 `raw_roe`, `raw_debt_ratio`가 전부 null → Quality 점수 반쪽
- EPS 모멘텀은 forward_eps 리비전 기반인데 국내 종목은 0.0 고정
- 네이버 `/finance/quarter` API에 분기별 EPS/ROE/부채비율이 있음을 확인
- FMP API (`FMP_API_KEY` 보유)로 미국 종목 분기 데이터 취득 가능

## 데이터 테이블

```sql
CREATE TABLE quarterly_financials (
    ticker      TEXT,
    period      TEXT,     -- 'YYYYQ1' ~ 'YYYYQ4', e.g. '2025Q1'
    eps         DOUBLE,
    roe         DOUBLE,   -- %
    debt_ratio  DOUBLE,   -- 부채비율 %
    revenue     DOUBLE,   -- 백만 원/달러
    op_income   DOUBLE,   -- 백만 원/달러
    source      TEXT,     -- 'naver' | 'fmp'
    PRIMARY KEY (ticker, period)
);
```

## 데이터 소스

| 유니버스 | 소스 | 엔드포인트 |
|----------|------|-----------|
| KOSPI200, KOSDAQ150 | Naver | `m.stock.naver.com/api/stock/{code}/finance/quarter` |
| SP500 | FMP API | `/v3/income-statement?period=quarter&limit=8` + `/v3/financial-ratios?period=quarter&limit=8` |

Naver: 최근 6분기 (실적 + 컨센서스 혼재, `isConsensus` 플래그로 구분 — 확정 실적만 저장)
FMP: 최근 8분기

## 신규 파일

- `core/data/naver_quarterly.py` — Naver 분기 스크래퍼
- `core/data/fmp_quarterly.py` — FMP 분기 스크래퍼
- `core/data/quarterly_provider.py` — 통합 인터페이스 (소스 분기)

## 배치 연동

`run_batch()` 흐름에 한 단계 추가:
```
펀더멘탈 페치 → [신규] quarterly sync → 팩터 계산
```

sync 로직 (append-only):
1. DB에서 해당 유니버스 티커들의 최신 period 조회
2. API에서 최신 period 확인
3. 새 분기 있으면 INSERT, 없으면 skip

## 팩터 개선

### Quality
- `universe_scorer.py`에서 `snap.roe` / `snap.debt_to_equity` 대신
  `quarterly_financials`의 최근 확정 분기 ROE/debt_ratio 사용
- 국내 종목: null → 실제 값으로 채워짐

### EPS 모멘텀
- 현재: forward_eps 1M/3M 리비전 (국내=0.0)
- 변경: 최근 분기 EPS vs 전년 동기 EPS → YoY 성장률
- 공식: `(eps_recent - eps_yoy) / |eps_yoy|`
- 전년 동기 데이터 없으면 0.0 (기존 동일)

## repository.py 변경

- `CREATE TABLE quarterly_financials` 추가 (마이그레이션)
- `upsert_quarterly_financials(rows)` 함수 추가
- `get_quarterly_financials(ticker, n_quarters)` 함수 추가

## 테스트

- `tests/test_naver_quarterly.py`: 삼성전자 파싱 검증
- `tests/test_fmp_quarterly.py`: AAPL 파싱 검증 (API 호출 mock)
- `tests/test_quarterly_eps_momentum.py`: YoY 계산 검증
