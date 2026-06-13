# UI 기능 이동 기록

목표는 이전 통합 화면에 모여 있던 기능을 상단 메뉴 구조에 맞춰 흡수하고, 사용자가 실제로 접근하는 화면 기준으로 정리하는 것이다. 현재 전용 route와 컴포넌트는 제거했다.

## 이동 원칙

- 포트폴리오 계산, 보유, 성과는 `/portfolio`와 `/portfolio/holdings`로 이동한다.
- 종목 차트, 뉴스, AI 요약, 스크리너는 `종목분석` 그룹으로 이동한다.
- 스케줄 실행, 초기 적재, 동기화 상태, 알림 job 상태는 `관리 > 작업관리`로 이동한다.
- 백테스트는 이미 `/backtest`가 있으므로 별도 진입점 없이 전략 화면에 둔다.
- 화면 조회 중 외부 API를 호출하는 기능은 hydrate/job 기반으로 바꾸고, 화면은 DB/cache를 우선 읽는다.

## 기능별 매핑

| 기능 | 현재 위치 | 현재 데이터/API | 이동 위치 | 상태 | 계획 |
| --- | --- | --- | --- | --- | --- |
| 시장 지표 스트립 | `MarketsPanel`, `IndexStrip` | `/api/quotes` | 포트폴리오, 종목분석, 전략 | 흡수됨 | 공통 `MarketStrip`으로 주요 화면 상단에 재사용한다. |
| 관심/보유 quick list | `WatchlistWidget` | `/api/holdings` | 포트폴리오, 관심종목 | 흡수됨 | 보유 기반 목록은 포트폴리오 보유 테이블, 관심종목은 `/watchlist`로 정리한다. |
| 단일 종목 차트/뉴스/AI | `CandleChart`, `NewsPanel`, `AIOverlay` | candles, news, AI API | 종목분석 | 흡수됨 | 종목 상세 화면에 차트, 뉴스, 명시 실행형 AI 요약을 통합했다. |
| 보유종목 동기화 | 보유종목 관리, 작업관리 | `holdingsApi.syncFromToss`, `syncFromKis` | 포트폴리오 보유관리, 작업관리 | 흡수됨 | Toss 수동 가져오기는 보유관리, 예약 동기화는 작업관리로 둔다. KIS는 현재 운영 화면에서 제외한다. |
| 리밸런싱 | `RebalancingPanel` | `/api/portfolio/rebalancing` | 포트폴리오 | 제거됨 | 목표 비중 기반 리밸런싱은 현재 운영 흐름에서 제외하고 포트폴리오 화면에서 제거했다. |
| 성과 분석 | `PerformancePanel` | `/api/portfolio/performance` | 포트폴리오 | 흡수됨 | 자산 추이와 별도로 Sharpe, MDD, 벤치마크 비교를 통합했다. |
| 거래 기록 | `TradeLogPanel` | trades API | 포트폴리오 보유관리 | 흡수됨 | 거래 로그와 source별 보유 데이터는 분리해서 관리한다. |
| 알림 조건/히스토리 | `AlertPanel` | alerts API, `alert_check` job | 종목분석, 관리 | 흡수됨 | 조건 생성은 종목 상세와 관리 화면에 두고, 최근 발생 이력은 관리 > 알림 관리에서 확인한다. |
| 종목 스크리너 | `/screener`, `/growth` | `/api/screener/scores` | 종목분석 | 흡수됨 | `/screener`, `/growth`에 이미 있으므로 해당 화면에서 유지한다. |
| 백테스트 | `/backtest` | `BacktestForm` | 전략 | 흡수됨 | `/backtest` 전략 화면에서 유지한다. |
| 계산기 도구 | `ToolsPanel` | fx API, 로컬 계산 | 전략 | 흡수됨 | 포지션 사이징, 환율 변환, 수익률 계산을 전략 화면의 보조 도구로 옮겼다. |
| 범용 AI 채팅 | `AiPanel` | AI stream API | 종목분석 | 제거됨 | 범용 채팅은 이식하지 않고 제거했다. 종목 상세의 명시 실행형 AI 요약만 유지한다. |

## 추천 구현 순서

1. Toss 주문/체결 내역을 거래 기록에 자동 적재할 수 있는지 구현 검토한다.
