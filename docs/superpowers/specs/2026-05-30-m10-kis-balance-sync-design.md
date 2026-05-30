# M10: KIS 계좌 잔고 동기화 설계

**날짜:** 2026-05-30  
**범위:** KIS 실계좌 잔고(국내+미장)를 수동 버튼으로 앱 holdings에 동기화

---

## 1. 목표

터미널 UI에서 버튼 한 번으로 KIS 실계좌 잔고를 가져와 holdings를 업데이트한다.  
기존 앱 종목은 삭제하지 않고, KIS 잔고 종목만 추가/수정한다.

**완료 조건:**
- `POST /api/holdings/sync-from-kis` 호출 시 국내+미장 잔고 동기화
- UI 버튼 클릭 → 토스트 "KIS 동기화 완료 — 추가 N개, 수정 N개"
- 테스트 6개 통과

---

## 2. 변경 범위

| 파일 | 변경 |
|------|------|
| `core/prices/kis.py` | `fetch_balance_domestic()` + `fetch_balance_overseas()` 추가 |
| `api/models.py` | `SyncResult` 모델 추가 |
| `api/routers/holdings.py` | `POST /api/holdings/sync-from-kis` 엔드포인트 추가 |
| `frontend/lib/api.ts` | `holdingsApi.syncFromKis()` 추가 |
| `frontend/components/terminal/widgets/PortfolioPanel.tsx` | "KIS 동기화" 버튼 + 결과 토스트 |
| `tests/test_kis_balance.py` | 신규 테스트 6개 |

---

## 3. KIS 잔고 API 스펙

**계좌 파라미터:** `KIS_ACCOUNT_NO=63241945-01`
- `CANO`: `63241945` (앞 8자리)
- `ACNT_PRDT_CD`: `01` (뒤 2자리)

### 3-1. 국내 잔고

**엔드포인트:** `GET /uapi/domestic-stock/v1/trading/inquire-balance`  
**tr_id:** `TTTC8434R` (실전)

요청 파라미터:
```
CANO=63241945, ACNT_PRDT_CD=01, AFHR_FLPR_YN=N, OFL_YN=,
INQR_DVSN=02, UNPR_DVSN=05, FUND_STTL_ICLD_YN=N,
FNCG_AMT_AUTO_RDPT_YN=N, PRCS_DVSN=01,
CTX_AREA_FK100=, CTX_AREA_NK100=
```

응답 `output1[]` 핵심 필드:
- `pdno` → 종목코드 (예: `005930`) → `005930.KS`로 변환
- `prdt_name` → 종목명
- `hldg_qty` → 보유수량
- `pchs_avg_pric` → 매입평균가 (KRW)

페이지네이션: 응답 헤더 `tr_cont`가 `"F"` 또는 `"M"`이면 다음 페이지 존재.  
`CTX_AREA_FK100`, `CTX_AREA_NK100`을 이전 응답의 `output3.ctx_area_fk100`, `output3.ctx_area_nk100`으로 교체 후 재요청.  
최대 10페이지 제한.

### 3-2. 해외 잔고

**엔드포인트:** `GET /uapi/overseas-stock/v1/trading/inquire-balance`  
**tr_id:** `TTTS3012R` (실전)

요청 파라미터:
```
CANO=63241945, ACNT_PRDT_CD=01,
OVRS_EXCG_CD=__ALL__, TR_CRCY_CD=USD,
CTX_AREA_FK200=, CTX_AREA_NK200=
```

응답 `output1[]` 핵심 필드:
- `ovrs_pdno` → 종목코드 (예: `AAPL`)
- `ovrs_item_name` → 종목명
- `ovrs_cblc_qty` → 잔고수량 (0이면 스킵)
- `pchs_avg_pric` → 매입평균가 (USD)
- `ovrs_excg_cd` → 거래소 (`NASD`→`NASDAQ`, `NYSE`→`NYSE`, `AMEX`→`AMEX`)

페이지네이션: `tr_cont` 헤더 동일 방식, `CTX_AREA_FK200`/`NK200` 사용.

---

## 4. 구현 상세

### 4-1. 잔고 조회 함수 (`core/prices/kis.py`)

```python
def fetch_balance_domestic() -> list[dict]:
    """KIS 국내 계좌 잔고 조회. 빈 리스트 = 토큰 없음 or 오류."""
    # Returns: [{"ticker": "005930.KS", "name": "삼성전자", "quantity": 10,
    #            "avg_price": 70000.0, "currency": "KRW", "market": "KRX"}]

def fetch_balance_overseas() -> list[dict]:
    """KIS 해외 계좌 잔고 조회 (전 거래소). 빈 리스트 = 토큰 없음 or 오류."""
    # Returns: [{"ticker": "AAPL", "name": "Apple Inc", "quantity": 5,
    #            "avg_price": 185.0, "currency": "USD", "market": "NASDAQ"}]
```

EXCD → market 변환:
```python
_EXCD_TO_MARKET_BALANCE = {
    "NASD": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX",
    "NAS": "NASDAQ",  "NYS": "NYSE",  "AMS": "AMEX",
}
```

### 4-2. `SyncResult` 모델 (`api/models.py`)

```python
class SyncResult(BaseModel):
    added: int
    updated: int
    errors: list[str]
```

### 4-3. 동기화 엔드포인트 (`api/routers/holdings.py`)

```python
@router.post("/sync-from-kis", response_model=SyncResult)
def sync_from_kis(user: CurrentUser = Depends(current_user)):
    from core.prices.kis import fetch_balance_domestic, fetch_balance_overseas
    
    existing = {h["ticker"] for h in repo.get_holdings(user.id)}
    added, updated, errors = 0, 0, []
    
    domestic = fetch_balance_domestic()
    overseas = fetch_balance_overseas()
    
    if not domestic and not overseas:
        errors.append("KIS 인증 실패 또는 잔고 없음")
        return SyncResult(added=0, updated=0, errors=errors)
    
    for item in domestic + overseas:
        try:
            repo.upsert_holding(user_id=user.id, **item)
            if item["ticker"] in existing:
                updated += 1
            else:
                added += 1
        except Exception as e:
            errors.append(f"{item['ticker']}: {e}")
    
    return SyncResult(added=added, updated=updated, errors=errors)
```

### 4-4. 프론트엔드 (`PortfolioPanel.tsx`)

- Positions 탭 헤더 우측에 "KIS 동기화" 버튼 (아이콘: RefreshCw)
- 클릭 → `POST /api/holdings/sync-from-kis` → 완료 시 토스트
  - 성공: "KIS 동기화 완료 — 추가 {added}개, 수정 {updated}개"
  - 오류: "동기화 오류: {errors[0]}"
- 로딩 중 버튼 비활성화 + 스피너

---

## 5. 에러 처리

| 상황 | 처리 |
|------|------|
| KIS 토큰 없음 | 빈 리스트 반환 → endpoint에서 errors에 메시지 |
| `rt_cd != "0"` | 해당 시장 빈 리스트 반환, errors에 기록 |
| `hldg_qty == 0` / `ovrs_cblc_qty == 0` | 스킵 |
| `upsert_holding` 실패 | errors에 추가, 나머지 계속 |
| 국내 성공 해외 실패 | 국내 결과 반영, errors에 해외 오류 |

---

## 6. 테스트 (`tests/test_kis_balance.py`)

| 테스트 | 검증 |
|--------|------|
| `test_fetch_balance_domestic_success` | 정상 응답 → `ticker=005930.KS`, `quantity`, `avg_price` 확인 |
| `test_fetch_balance_domestic_empty` | `output1=[]` → 빈 리스트 |
| `test_fetch_balance_overseas_success` | 정상 응답 + `NASD`→`NASDAQ` market 변환 확인 |
| `test_fetch_balance_overseas_skips_zero_qty` | `ovrs_cblc_qty="0"` → 스킵 |
| `test_sync_endpoint_upserts_holdings` | balance mock → `upsert_holding` 호출 횟수·인자 검증 |
| `test_sync_endpoint_no_token` | 토큰 None → `errors` 포함, 200 응답 |

---

## 7. 제외 범위 (YAGNI)

- 자동 주기 동기화 — 수동 버튼으로 충분
- 일본/홍콩 등 비US 해외 잔고 — `OVRS_EXCG_CD=__ALL__`로 KIS가 지원하는 전체 포함이나 UI 표시는 US만
- 현금 잔고(예수금) 동기화 — holdings와 별도 관심사
- 동기화 이력 로깅 — 별도 마일스톤
