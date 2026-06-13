# 데이터 Provider 정책

## 원칙

- 화면 조회 API는 DB/cache를 우선 읽고 외부 provider를 자동 호출하지 않는다.
- 외부 호출은 초기 적재, 스케줄 작업, 수동 갱신, hydrate 같은 명시적 작업에서만 수행한다.
- fallback은 조용히 값을 대체하지 않는다. 사용한 경우 `source`, `fallback_used`, `reason`, `as_of/fetched_at`을 노출한다.
- 품질이 다른 데이터는 fallback하지 않고 `데이터 없음` 또는 `데이터 보강 필요`를 표시한다.

## Primary 역할

| 영역 | Primary | 비고 |
|---|---|---|
| 시세/환율/OHLCV | Toss OpenAPI + DuckDB cache | 페이지는 cache만 읽고, 수집 작업이 cache를 채운다. |
| 보유종목/현금 | Toss OpenAPI + manual source | source별 저장, 포트폴리오 계산에서만 합산한다. |
| 미국 valuation | Finviz/StockAnalysis 수집 작업 -> `fundamental_snapshots` | 관심종목/종목분석 화면은 snapshot만 읽는다. |
| 국내 valuation | Naver Finance/OpenDART 수집 작업 -> `quant_scores`, `fundamental_snapshots` | DART 키가 없으면 coverage 경고로 표시한다. |
| 미국 목표주가 | FMP 명시 갱신 | 한도/요금제 제한이 있으면 상태를 표시한다. |
| 국내 목표주가 | KIS `invest-opinion` 명시 갱신 | Toss가 제공하지 않는 영역이라 KIS를 유지한다. |
| 뉴스 | RSS/FMP 등 별도 정책 | 시세/valuation fallback과 분리한다. |

## KIS 유지 범위

KIS는 기본 시세, 환율, OHLCV, 보유종목 동기화 provider로 사용하지 않는다. 기본 provider는 Toss다.

KIS를 유지하는 이유는 국내 목표주가/투자의견 API 때문이다. 현재 `core/data/price_target_consensus.py`에서 국내 티커의 최근 6개월 증권사 목표주가를 집계한다.

## 명시 적재 작업

- `fundamental_snapshots_hydrate`: 관심종목과 보유종목에서 미국/해외 티커를 모아 Finviz/StockAnalysis snapshot을 `fundamental_snapshots`에 저장한다.
- 스케줄: 매일 08:20 KST.
- 수동 실행: `/jobs`의 `관심/보유 펀더멘털 적재` 작업에서 실행한다.
- 국내 티커는 이 작업에서 제외한다. 국내 valuation은 Naver/OpenDART 배치가 담당한다.

## 제거/축소 후보

- KIS 잔고 동기화 UI/API: Toss 동기화로 대체되었으므로 제거 후보.
- yfinance 시세/OHLCV fallback: 조용한 fallback으로 사용하지 않는다.
- 화면 조회 중 Finviz/StockAnalysis on-demand 호출: hydrate/job 기반 수집으로 이동한다.
- 과도한 뉴스 fallback: primary/secondary 정도로 단순화한다.

## UI 표시 필수값

- 데이터 출처: `source`
- 기준일: `as_of` 또는 `fetched_at`
- 최신성: `stale`
- 대체 사용 여부: `fallback_used`
- 실패 사유: `last_error` 또는 `reason`
