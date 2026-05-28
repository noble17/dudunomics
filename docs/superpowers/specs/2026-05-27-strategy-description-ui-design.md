# 전략 설명 UI 설계 (A+B 조합)

**날짜:** 2026-05-27  
**범위:** 백테스트 폼의 전략 선택 UX 개선

---

## 목표

현재 전략 드롭다운은 이름만 표시함. 사용자가 전략이 무엇을 하는지 모른 채 선택해야 함.  
**각 전략의 아이콘 + 설명 + 태그를 드롭다운과 선택 후 카드 두 곳에 표시한다.**

---

## 동작 방식

### 드롭다운 열면 (Option B)

각 전략 항목에 이모지 아이콘 + 1줄 요약 + 카테고리 배지를 표시한다. 선택 전에 미리 비교 가능.

```
[📈 SMA Crossover       골든/데드 크로스 단일 종목 매매  [단일종목]]
[⚖️ Equal Weight        동일 비중 분산 Buy & Hold       [다종목]  ]
[🔬 Forward 팩터 리밸런싱  EPS·PER 상위 종목 월 리밸런싱   [펀더멘탈]]
[🧬 하이브리드 (펀더멘탈+SMA) 팩터 선별 → SMA 게이트 필터   [고급]    ]
```

### 전략 선택 후 (Option A)

드롭다운 아래에 설명 카드가 확장된다:
- 이모지 아이콘 + 전략명 + 카테고리 배지
- 1-2줄 상세 설명
- 메타 태그: 복잡도, 리밸런싱 주기, 팩터 여부

---

## 전략별 콘텐츠

| 전략 | 아이콘 | 1줄 설명 | 태그 |
|------|--------|---------|------|
| SMA Crossover | 📈 | 골든/데드 크로스로 단일 종목 매수·매도 | 단일종목 |
| Equal Weight | ⚖️ | 여러 종목에 동일한 비중으로 분산 Buy & Hold | 다종목, 초보 친화적 |
| Forward 팩터 리밸런싱 | 🔬 | EPS·PER 팩터로 상위 종목 선별 후 월별 리밸런싱 | 펀더멘탈, 월 리밸런싱 |
| 하이브리드 (펀더멘탈+SMA) | 🧬 | 팩터로 종목 선별 후 SMA 골든크로스 종목만 보유 | 고급, 하이브리드 |

---

## 데이터 흐름

백엔드 전략 클래스 → API `/strategies` → 프론트 `StrategyDef` → `backtest-form.tsx`

`description`, `icon`, `tags` 필드를 백엔드 `Strategy` 클래스에 `ClassVar`로 추가. 프론트는 Optional로 받아 있으면 렌더링.

---

## 변경 파일

**백엔드 (6개)**
- `core/strategies/base.py` — `description`, `icon`, `tags` ClassVar 추가, `list_strategies()`에 포함
- `core/strategies/sma_crossover.py` — 콘텐츠 채우기
- `core/strategies/equal_weight.py` — 콘텐츠 채우기
- `core/strategies/factor_rebalance.py` — 콘텐츠 채우기
- `core/strategies/hybrid_factor_sma.py` — 콘텐츠 채우기

**프론트엔드 (2개)**
- `frontend/lib/types.ts` — `StrategyDef`에 `description?`, `icon?`, `tags?` 추가
- `frontend/components/backtest/backtest-form.tsx` — 드롭다운 아이템 + 설명 카드 렌더링

---

## 호환성

- `description`/`icon`/`tags` 없는 전략은 기존 방식으로 폴백 (Optional)
- API 응답 필드 추가이므로 기존 클라이언트 깨지지 않음
