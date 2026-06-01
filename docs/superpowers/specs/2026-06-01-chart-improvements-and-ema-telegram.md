# 스펙: 차트 가시성 개선 + EMA 골든크로스 Telegram 알람

**날짜:** 2026-06-01  
**범위:** 프론트엔드 차트 2개 수정 + 백엔드 유니버스 스캔 잡 신규

---

## 1. EPS 예상 선 색상 개선 (`price-chart.tsx`)

### 문제
`주가&EPS` 탭의 예상 EPS 점선 색상(`#6b7280`, 회색)이 어두운 배경에서 잘 안 보임.

### 변경
- `eps_est` Line stroke: `#6b7280` → `#fbbf24` (amber)
- 주가(파랑 `#3b82f6`) · 실제 EPS(초록 `#22c55e`) · 예상 EPS(amber)로 3색 명확히 구분

### 조건
- 미래 날짜에는 주가 선을 그리지 않음 (현재 `price: null` 동작 유지)
- 예상 EPS만 amber 점선으로 연장

---

## 2. 성장 차트 예상 막대 색상 개선 (`growth-chart.tsx`)

### 문제
예상(`is_estimate: true`) 막대의 `var(--muted)` 색이 다크 테마에서 거의 보이지 않음.

### 변경
- 예상 막대 fill: `var(--muted)` → `rgba(59, 130, 246, 0.45)` (반투명 파랑)
- 실제 데이터(진파랑 `#3b82f6`) vs 예상(연파랑 반투명) 시각적 구분

---

## 3. EMA 골든크로스 Telegram 유니버스 스캔

### 개요
사용자 등록 없이 전체 스크리너 유니버스를 자동 스캔, 종가 기준 EMA 골든크로스 감지 시 Telegram 발송.

### 스캔 대상
- KOSPI200 (`data/kospi200_tickers.json`, 200개)
- KOSDAQ150 (`data/kosdaq150_tickers.json`, 150개)
- S&P500 (`data/sp500_tickers.json`, 503개)
- NASDAQ100 (`data/nasdaq100_tickers.json`, 101개)
- 중복 제거 후 약 900개 티커

### 실행 시점 (종가 기준 APScheduler cron)
| 시장 | 실행 시각 (KST) | 이유 |
|------|----------------|------|
| 국장 (KR) | 매일 16:00 | KOSPI/KOSDAQ 종가 15:30 확정 후 |
| 미장 (US) | 매일 07:00 | NYSE/NASDAQ 종가 06:00 확정 후 |

### 골든크로스 조건 (EMA 기준)
```
전일: EMA5 ≤ EMA20
당일: EMA5 > EMA20
```
- EMA 계산: `pandas` `ewm(span=N, adjust=False)`
- OHLCV 조회: 최근 90 거래일 (EMA 워밍업 포함)

### 7일 반복 메커니즘
1. **신규 감지**: 골든크로스 발생 → `golden_cross_events` 테이블에 INSERT, 1일차 Telegram 발송
2. **유지 확인**: 매일 스캔 시 `EMA5 > EMA20` 유지 중이고 `first_detected_at` ≤ 7일 → N일차 Telegram 발송
3. **종료**: `EMA5 ≤ EMA20` (데드크로스 전환) 또는 `first_detected_at` > 7일 → `golden_cross_events`에서 해당 행 삭제 (다음 골든크로스 때 재감지 가능)

### DB 테이블 `golden_cross_events`
```sql
CREATE TABLE IF NOT EXISTS golden_cross_events (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    market      TEXT NOT NULL,          -- 'KR' | 'US'
    name        TEXT,                   -- 종목명 (표시용)
    first_detected_at  DATE NOT NULL,
    last_sent_at       TIMESTAMP,
    day_count   INTEGER DEFAULT 1,
    UNIQUE(ticker)
);
```

### Telegram 메시지 형식
시장별로 1개 메시지 발송. 신규 / 유지 섹션으로 구분.

```
📈 EMA 골든크로스 (국장 · 2026-06-01)

🆕 신규
• 삼성전자 — 1일차
  현재가 72,500원 | EMA5 72,100 | EMA20 71,200 | EMA60 69,800

🔄 유지 중
• SK하이닉스 — 3일차
  현재가 181,000원 | EMA5 179,500 | EMA20 177,800 | EMA60 173,100
```

- 신규/유지 모두 없으면 Telegram 미발송 (무음)
- 한 메시지 최대 4096자 제한 초과 시 자동 분할 발송

### 새 파일
| 파일 | 역할 |
|------|------|
| `core/telegram.py` | `send_telegram(text: str)` — httpx로 Bot API 호출 |
| `core/ema_scan.py` | `run_ema_scan(market: str)` — 스캔 + DB + Telegram |

### 수정 파일
| 파일 | 변경 내용 |
|------|----------|
| `core/scheduler.py` | `ema_scan_kr_job` (16:00 cron), `ema_scan_us_job` (07:00 cron) 추가 |
| `core/repository.py` | `golden_cross_events` 테이블 생성 + CRUD 함수 |

### 환경변수
```
TELEGRAM_BOT_TOKEN=<BotFather 발급 토큰>
TELEGRAM_CHAT_ID=<개인 Chat ID>
```
미설정 시 `core/telegram.py`에서 warning 로그 후 스킵 (서버 기동은 정상 유지).

### 오류 처리
- 개별 티커 OHLCV 조회 실패 → 해당 티커 스킵, 로그 기록, 나머지 계속
- Telegram 전송 실패 → 로그 기록, 재시도 없음 (다음 날 재발송)
- 전체 잡 오류 → `log.error` 후 종료 (스케줄러 유지)
