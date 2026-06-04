# Valuation Overhaul — EV/EBITDA 통합 밸류에이션 설계

**날짜**: 2026-05-31  
**상태**: 승인 대기

---

## 배경 및 목적

현재 밸류에이션 스코어는 PBR + PER 조합을 사용한다. PBR은 무형자산 비중이 큰 현대 기업(테크, M&A 기업, 자사주 매입 기업)에서 신뢰도가 낮고, 자본잠식 기업에서는 아예 계산 불가하다. DELL처럼 AI 서버 사업으로 강한 현금흐름을 내면서도 PBR이 음수인 기업이 스코어에서 불이익을 받는 문제를 해결한다.

---

## 범위

- 밸류에이션 팩터를 EV/EBITDA + PER 통일
- 자본잠식(음수 PBR) 기업 명시적 플래그
- FCF Yield 계산 (진짜 OCF - CapEx / Market Cap)
- PEG, 섹터/산업 정보 추가
- yfinance 완전 제거

---

## 아키텍처

### 데이터 흐름

```
Finviz 스냅샷 (기존 페이지, 파싱 확장)
  ├── ev_ebitda     (신규)
  ├── peg           (신규)
  ├── market_cap_m  (신규, 단위: 백만 USD)
  ├── sector        (신규)
  ├── industry      (신규)
  └── negative_book_value (신규, P/B 원문이 "-"이면 True)

StockAnalysis 현금흐름표 (기존 페이지, 파싱 확장)
  ├── operating_cashflow  (기존)
  └── capex               (신규)

fundamentals_extended.py
  └── fcf_yield = (operating_cashflow - capex) / (market_cap_m × 1_000_000)
      (OCF 또는 CapEx 중 하나라도 None이면 None)

universe_scorer.py — 밸류에이션 분기
  ├── EV/EBITDA 있음 → EV/EBITDA_z × 0.6 + PER_z × 0.4
  └── EV/EBITDA 없음 → PER_z 단독 (fallback)

PBR → 스코어링에서 완전 제거, raw_pbr은 표시용으로만 DB 유지
```

---

## 비즈니스 룰

### 1. PBR 음수 감지

Finviz `P/B` 셀이 `"-"` 문자열인 경우 → `negative_book_value = True`, `price_to_book = None`.  
양수 PBR만 `raw_pbr`에 저장. 스코어링 로직에서는 PBR을 전혀 사용하지 않음(표시 전용).

### 2. 통합 밸류에이션 공식

```
모든 종목:
  if ev_ebitda is not None and ev_ebitda > 0:
      val_z = winsorize_zscore(ev_ebitda) × 0.6  +  winsorize_zscore(fwd_pe) × 0.4
  else:
      val_z = winsorize_zscore(fwd_pe)

낮을수록 저평가 → 백분위 변환 시 ascending=False
```

EV/EBITDA ≤ 0 (적자·음수 EBITDA) → ev_ebitda 제외, PER 단독 fallback.

### 3. FCF Yield

```python
fcf = operating_cashflow - capex   # 단위: USD 절대값
fcf_yield = fcf / (market_cap_m * 1_000_000)
```

- `market_cap_m` 또는 `operating_cashflow` 또는 `capex` 중 하나라도 None → `fcf_yield = None`
- CapEx는 항상 음수(현금 유출)로 기록되므로 `capex` 파싱 시 절댓값으로 저장

### 4. PEG

- `raw_peg`: Finviz에서 직접 파싱 (PEG 5-year expected)
- `peg_undervalued`: `0 < raw_peg < 1.0` → True

### 5. Earnings Revision

기존 `ForwardEpsMomentumFactor` slope 값을 재활용:
- `eps_revision_up = True` if `raw_eps_momentum > 0`

### 6. 자본잠식 플래그 API 응답

```json
{
  "negative_book_value": true,
  "pbr_flag": "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
}
```

### 7. yfinance 제거

`fundamentals_extended.py` 77~119줄 전체 삭제 (yfinance fallback 2개소).  
PBR/ROE 미제공 케이스는 `None`으로 처리. 스코어링 로직이 이를 EV/EBITDA 기반으로 자연스럽게 우회.

---

## 변경 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `core/data/fundamentals_scraper.py` | `FundamentalsSnapshot`에 `ev_ebitda`, `peg`, `market_cap_m`, `capex`, `sector`, `industry`, `negative_book_value` 추가. `_fetch_finviz()`에서 파싱. `_supplement_stockanalysis()`에서 capex 추가 파싱. |
| `core/data/fundamentals_extended.py` | `ExtendedSnapshot`에 신규 필드 추가. yfinance 완전 제거. `fcf_yield` 계산 추가. |
| `core/factors/valuation.py` | PBR 제거. `compute_valuation_zscore(ev_ebitda, fwd_pe)` 함수로 교체. |
| `core/scoring/universe_scorer.py` | 밸류에이션 분기 로직 적용. `raw_ev_ebitda`, `raw_peg`, `raw_fcf_yield`, `negative_book_value`, `sector`, `industry` 컬럼 추가. |
| `core/repository.py` | `quant_scores` 마이그레이션: `raw_ev_ebitda DOUBLE`, `raw_peg DOUBLE`, `raw_fcf_yield DOUBLE`, `negative_book_value BOOLEAN`, `sector TEXT`, `industry TEXT` 추가. |
| `api/models.py` | `QuantScoreOut`에 신규 필드 노출. |
| `tests/test_valuation.py` | DELL 시나리오(negative_book_value, EPS 상향) 단위 테스트. |

---

## DB 스키마 변경

```sql
ALTER TABLE quant_scores ADD COLUMN raw_ev_ebitda    DOUBLE;
ALTER TABLE quant_scores ADD COLUMN raw_peg          DOUBLE;
ALTER TABLE quant_scores ADD COLUMN raw_fcf_yield    DOUBLE;
ALTER TABLE quant_scores ADD COLUMN negative_book_value BOOLEAN DEFAULT FALSE;
ALTER TABLE quant_scores ADD COLUMN sector           TEXT;
ALTER TABLE quant_scores ADD COLUMN industry         TEXT;
```

기존 데이터는 모두 NULL로 유지 (배치 재실행 시 채워짐).

---

## API 노출 신규 필드

`GET /api/screener/scores` 응답의 `QuantScoreOut` 추가 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `negative_book_value` | `bool` | 자본잠식 / 음수 순자산 여부 |
| `pbr_flag` | `str \| None` | 자본잠식 안내 문구 |
| `raw_ev_ebitda` | `float \| None` | EV/EBITDA 원값 |
| `raw_peg` | `float \| None` | PEG 원값 |
| `peg_undervalued` | `bool` | PEG < 1 저평가 플래그 |
| `raw_fcf_yield` | `float \| None` | FCF Yield (0.05 = 5%) |
| `eps_revision_up` | `bool` | EPS 추정치 상향 여부 |
| `sector` | `str \| None` | 섹터 (e.g. "Technology") |
| `industry` | `str \| None` | 산업 (e.g. "Computer Hardware") |

---

## 테스트 시나리오

### DELL 가상 케이스

```python
snap = ExtendedSnapshot(
    ticker="DELL",
    negative_book_value=True,
    forward_pe=12.0,
    ev_ebitda=8.5,          # AI 서버 사업으로 낮은 EV/EBITDA
    peg=0.8,                # PEG < 1 → 저평가
    forward_eps=8.5,
    operating_cashflow=5_000_000_000,
    capex=1_200_000_000,
    market_cap_m=45_000,    # 4,500억 USD
    sector="Technology",
    industry="Computer Hardware",
)
# 기대값:
# fcf_yield ≈ 0.084 (8.4%)
# valuation_zscore: EV/EBITDA 기반 계산
# peg_undervalued: True
# pbr_flag: "자본잠식형 우량주 가능성 (M&A·자사주매입 기업)"
```

### 에러 없음 검증

- `ev_ebitda = None`인 종목 → PER 단독 fallback, 예외 없음
- `capex = None`인 종목 → `fcf_yield = None`, 예외 없음
- `market_cap_m = None`인 종목 → `fcf_yield = None`, 예외 없음

---

## 스코프 외

- 금융주(은행·보험) 별도 PBR 처리: YAGNI. EV/EBITDA 없는 금융주는 PER fallback으로 자연 처리.
- StockAnalysis CapEx 파싱 실패 시: `capex = None`으로 처리, `fcf_yield = None`. 배치 중단 없음.
