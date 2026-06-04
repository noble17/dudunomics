# 성장주 타이밍 설명 강화 및 목표주가 Fallback 설계

## 목표

`/growth`의 `TIMING CHECK`를 단순 boolean 표시에서 설명 가능한 단계형 판정으로 확장한다. 미국 목표주가 조회는 FMP가 특정 종목을 지원하지 않거나 호출 한도에 도달했을 때 기존 Finviz 상세 페이지를 2차 소스로 재사용한다.

## 범위

- 거래량을 직전 20거래일 평균 대비 비율과 캔들 방향으로 분류한다.
- 최근 5거래일 내 강한 음봉 거래량도 위험 신호로 반영한다.
- Wilder RSI 14를 타이밍 판정에 추가한다.
- `적합`이 `관망`으로 하향될 때 reason code와 설명을 반환한다.
- UI에서 긍정 신호, 주의 신호, 하향 사유를 구분해 표시한다.
- 미국 목표주가는 `FMP -> Finviz -> StockAnalysis` 순서로 조회하고 실제 사용 소스를 표시한다.
- 국내 목표주가는 기존 KIS 흐름을 유지한다.

## 거래량 판정

현재 거래량은 당일을 제외한 직전 20거래일 평균과 비교한다.

```text
volume_ratio = today_volume / previous_20_day_average

quiet      volume_ratio < 0.8
normal     0.8 <= volume_ratio < 1.0
increased  1.0 <= volume_ratio < 1.5
strong     1.5 <= volume_ratio < 2.0
explosive  2.0 <= volume_ratio
```

종가와 시가를 비교해 `bullish`, `bearish`, `flat` 방향을 계산한다.

```text
bullish + ratio >= 1.0  매수세 유입
bullish + ratio >= 1.5  강한 매수세
bearish + ratio >= 1.0  매도 압력 주의
bearish + ratio >= 1.5  강한 매도 압력
```

최근 5거래일도 같은 방식으로 검사한다. 최근 5거래일 내 `bearish + ratio >= 1.5`가 있으면 당일 거래량이 평범하더라도 `recent_bearish_volume_spike` 위험 신호를 반환한다. 기존 `volume_explosion` 필드는 호환성을 위해 유지하되 `bullish + ratio >= 1.5` 의미로 제한한다.

## RSI 판정

RSI는 Wilder smoothing 기반 14거래일 지표로 계산한다.

```text
oversold             RSI < 30
neutral              30 <= RSI < 70
overheated           70 <= RSI < 80
extreme_overheated   80 <= RSI
```

`overheated`는 주의 설명만 추가한다. 강한 상승 추세에서 RSI 70 이상이 지속될 수 있기 때문이다. `extreme_overheated`는 추격 매수 위험이 크므로 최종 상태를 `관망`으로 하향한다.

## 최종 타이밍 상태

기본 진입 적합 조건은 아래와 같다.

```text
EMA20 > EMA50 > EMA200
AND 현재가가 EMA20 또는 EMA50의 +/-3% 범위
AND 현재가 > EMA200
AND bullish volume_ratio >= 1.0
```

기존 `1.5배` 조건은 강한 신호를 식별하는 데 사용하고, 진입 적합의 최소 조건은 `1.0배`로 완화한다.

아래 조건이 있으면 기본 진입 적합 조건을 충족해도 `watch`로 하향한다.

```text
RSI >= 80
OR today bearish volume_ratio >= 1.0
OR recent 5 day bearish volume_ratio >= 1.5
```

정배열이 아니면 기존처럼 `unsuitable`이다. 정배열이지만 기본 진입 적합 조건이 부족하면 `watch`다.

## 설명 가능한 판정

타이밍 API는 최종 상태 외에 아래 정보를 반환한다.

```text
positive_reasons: 긍정 신호 목록
warning_reasons: 주의 신호 목록
downgrade_reasons: suitable 후보를 watch로 낮춘 직접 사유 목록
```

각 항목은 안정적인 `code`, UI 표시용 `message`, `severity`를 가진다. 예시는 아래와 같다.

```json
{
  "code": "extreme_rsi",
  "message": "RSI 82.49로 극단적 과열 구간입니다. 추격 매수 위험으로 관망 처리했습니다.",
  "severity": "warning"
}
```

## 미국 목표주가 Fallback

미국 종목은 아래 순서로 조회한다.

```text
FMP -> Finviz -> StockAnalysis -> 안내 메시지
```

FMP가 `subscription_limited`, `no_data`, `rate_limited`, `temporary_error`, `missing_key`를 반환하면 Finviz 상세 페이지의 snapshot `Target Price`를 사용한다. 기존 Finviz 펀더멘털 수집과 동일한 URL 및 24시간 캐시를 재사용한다. Finviz도 실패하면 StockAnalysis 공개 forecast 페이지를 선택 종목에 한해 저빈도로 조회한다. FMP가 정상 데이터를 반환하면 fallback을 호출하지 않는다.

Finviz의 `Target Price`는 평균 목표가로 표시하고, 중앙값·최저·최고·애널리스트 수가 제공되지 않는 경우 `None`으로 둔다. StockAnalysis도 실패하면 기존 수동 목표가 입력을 유지한다. proxy, CAPTCHA 회피, 차단 우회는 하지 않는다.

최종 응답은 실제 사용한 소스와 fallback 여부를 포함한다.

```text
consensus_source: FMP | FINVIZ | STOCKANALYSIS | KIS
fallback_used: boolean
consensus_attempts: [{ source, status }]
```

StockAnalysis도 데이터를 반환하지 못하면 사용자에게 각 소스의 상태를 요약한다. 한 소스의 실패가 다른 종목 조회를 막지 않도록 종목별 캐시를 유지한다. provider 전체 호출 한도 상태만 당일 전역 캐시로 관리한다.

## UI

`TIMING CHECK`에 아래 내용을 추가한다.

- 현재 거래량, 20일 평균, 배율
- 거래량 단계와 양봉·음봉 방향
- 최근 5거래일 내 강한 음봉 거래량 경고
- RSI 14 값과 단계
- 긍정 신호 목록
- 주의 신호 목록
- `관망`으로 하향된 경우 별도 `관망 전환 사유` 박스

목표주가 카드에는 실제 데이터 소스를 표시한다. fallback이 사용되면 `FMP 제한 -> Finviz 대체 조회`와 같이 표시한다.

## 검증

- 합성 OHLCV로 거래량 단계, 방향, 최근 5일 경고, Wilder RSI, 상태 하향을 단위 테스트한다.
- FMP 정상 시 fallback 미호출, FMP 제한 시 Finviz 호출, 모든 소스 실패 시 상태 요약을 단위 테스트한다.
- API 계약 테스트로 reason 구조와 fallback 메타데이터를 검증한다.
- `/growth`에서 MU와 정상 미국 종목을 선택해 안내 문구와 실제 사용 소스를 브라우저에서 확인한다.
