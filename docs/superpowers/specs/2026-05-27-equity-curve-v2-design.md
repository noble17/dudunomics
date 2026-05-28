# 자산 추이 차트 v2 설계

**날짜**: 2026-05-27  
**상태**: 승인

---

## 개요

기존 `EquityCurve` 컴포넌트의 버그를 수정하고, 시간 범위 필터·통계 행·줌 브러시·이벤트 시스템을 추가한다.

---

## 1. 버그 수정

### 1-1. Tooltip 동일 값 문제
- **원인**: `ts.slice(0, 10)` 으로 날짜만 저장하면서 같은 날짜의 여러 포인트가 동일 키를 갖게 되어 Recharts가 첫 번째 값만 표시.
- **수정**: `data` 배열의 `ts` 필드에 ISO timestamp 전체(`h.ts`)를 그대로 사용. X축 `tickFormatter`에서 표시용 포맷만 변환.

### 1-2. X축 시간 미표시
- **수정**: `tickFormatter`를 `"MM-DD HH:mm"` 형태로 변경.

---

## 2. 프론트엔드 — EquityCurve 컴포넌트 재구성

### 2-1. 범위 버튼
- 버튼: `1H | 6H | 24H | 3D | 7D | 30D`
- 위치: 카드 헤더 우측
- 동작: 클릭 시 `history` 배열을 `now - N시간` 기준으로 클라이언트 필터링
- 기본값: `7D`
- 30D 커버를 위해 `portfolioApi.history()` limit을 `8640`으로 변경 (5분 × 12 × 24 × 30)

### 2-2. 통계 행 (A1 레이아웃)
범위 버튼 아래, 차트 위에 가로 4칸 셀:

| 현재 | 변동 | 최고 | 최저 |
|------|------|------|------|
| 선택 범위 마지막 `total_with_cash_krw` | 마지막 − 첫 번째 | 범위 내 max | 범위 내 min |

- 변동이 양수면 `text-gain`, 음수면 `text-loss`

### 2-3. 메인 차트
- **데이터**: 필터링된 범위의 `{ ts, equity, total }` 배열
- **X축**: `tickFormatter`로 `"MM-DD HH:mm"` 표시, `tickCount` 6
- **이벤트 선**: 범위 내 이벤트마다 Recharts `ReferenceLine` (주황 점선 `#E8812A`, `strokeDasharray="4 3"`)
  - label: 이벤트 `label` 텍스트 (차트 상단)

### 2-4. 줌 브러시
- Recharts `Brush` 컴포넌트를 `LineChart` 내부에 추가
- `dataKey="ts"`, `height=24`, `stroke="#1375EC"`
- 브러시 이동 시 메인 차트 표시 범위가 연동됨 (Recharts 기본 동작)
- 통계 행 값은 브러시 범위가 아닌 **범위 버튼 기준**으로 계산 (단순화)

### 2-5. 이벤트 섹션
차트 카드 하단에 구분선 후 배치:
- 헤더: `이벤트` 라벨 + `+ 이벤트 추가` 버튼 (우측)
- 이벤트 목록: 행마다 `[아이콘] [라벨] · [날짜] · [타입]` / `[금액] [삭제]`
  - 입금 금액: `text-gain` (+N만원)
  - 출금 금액: `text-loss` (-N만원)
  - 금액 0 / 기타: 표시 생략
- `+ 이벤트 추가` 클릭 시 인라인 폼 토글:
  - 필드: 날짜/시간(`datetime-local`), 라벨(text), 금액(number, 선택), 타입(입금/출금/기타 select)
  - 저장 / 취소 버튼

---

## 3. 백엔드

### 3-1. DB 스키마 (`core/repository.py`)

`_init_schema`의 `ddl` 문자열 블록(기존 테이블들과 같은 위치)에 추가:

```sql
CREATE TABLE IF NOT EXISTS portfolio_events (
    id INTEGER PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    label TEXT NOT NULL,
    amount INTEGER DEFAULT 0,
    type TEXT DEFAULT '기타'
);
CREATE SEQUENCE IF NOT EXISTS portfolio_events_id_seq START 1;
```

### 3-2. Repository 함수

```python
def get_events() -> list[dict]
def insert_event(ts, label, amount, type) -> int
def delete_event(id) -> None
```

### 3-3. API 모델 (`api/models.py`)

```python
class EventIn(BaseModel):
    ts: datetime
    label: str
    amount: int = 0
    type: str = "기타"

class EventOut(EventIn):
    id: int
```

### 3-4. 라우터 (`api/routers/portfolio.py`)

```
GET    /api/portfolio/events        → list[EventOut]
POST   /api/portfolio/events        → EventOut
DELETE /api/portfolio/events/{id}   → {"ok": True}
```

인증: `require_auth` 의존성 적용.

---

## 4. 데이터 흐름

```
portfolio/page.tsx
  └─ useSWR("/api/portfolio/events", ...) → EventOut[]
  └─ useSWR("/api/portfolio/history?limit=8640", ...) → SnapshotHistory[]

EquityCurve({ history, events })
  ├─ 범위 버튼 → filteredHistory (클라이언트 필터)
  ├─ 통계 행 ← filteredHistory에서 계산
  ├─ LineChart
  │   ├─ Line(equity), Line(total)
  │   ├─ ReferenceLine × events (범위 내)
  │   └─ Brush
  └─ 이벤트 섹션 (CRUD)
```

---

## 5. 파일 변경 목록

| 파일 | 변경 |
|------|------|
| `core/repository.py` | `portfolio_events` 테이블 + 시퀀스 DDL, 3개 함수 추가 |
| `api/models.py` | `EventIn`, `EventOut` 추가 |
| `api/routers/portfolio.py` | 이벤트 3개 엔드포인트 추가 |
| `frontend/lib/types.ts` | `EventOut` 타입 추가 |
| `frontend/lib/api.ts` | `portfolioApi.events`, `portfolioApi.addEvent`, `portfolioApi.deleteEvent` 추가, `history` limit 변경 |
| `frontend/app/portfolio/page.tsx` | events SWR 훅 추가, `EquityCurve`에 props 전달 |
| `frontend/components/portfolio/equity-curve.tsx` | 전면 재작성 |

---

## 6. 범위 외

- 이벤트 수정(edit): 삭제 후 재등록으로 대체
- 이벤트 아이콘 커스터마이징: 타입별 고정 이모지(💰입금, 💳출금, 📌기타)
- 브러시 범위 연동 통계: 구현 복잡도 대비 효과 낮아 제외
