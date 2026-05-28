# Strategy Description UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백테스트 전략 드롭다운에 이모지 아이콘 + 1줄 요약 + 태그를 표시하고, 선택 후 설명 카드를 확장한다.

**Architecture:** 백엔드 Strategy 클래스에 `description`/`icon`/`tags` ClassVar를 추가하고 `/strategies` API에 노출. 프론트엔드는 Optional로 받아 드롭다운 아이템(Option B)과 선택 후 카드(Option A) 두 곳에 렌더링.

**Tech Stack:** Python/FastAPI (백엔드), Next.js/React/TypeScript + Tailwind + shadcn/ui (프론트엔드), pytest (테스트)

---

## File Map

| 파일 | 변경 |
|------|------|
| `core/strategies/base.py` | `description`, `icon`, `tags` ClassVar 추가, `list_strategies()` 업데이트 |
| `api/models.py` | `StrategiesOut`에 Optional 필드 3개 추가 |
| `core/strategies/sma_crossover.py` | 콘텐츠 채우기 |
| `core/strategies/equal_weight.py` | 콘텐츠 채우기 |
| `core/strategies/factor_rebalance.py` | 콘텐츠 채우기 |
| `core/strategies/hybrid_factor_sma.py` | 콘텐츠 채우기 |
| `tests/test_backtest_api.py` | `description`/`icon`/`tags` 필드 검증 테스트 추가 |
| `frontend/lib/types.ts` | `StrategyDef`에 Optional 필드 추가 |
| `frontend/components/backtest/backtest-form.tsx` | 드롭다운 아이템 + 선택 후 카드 렌더링 |

---

## Task 1: 실패 테스트 작성

**Files:**
- Modify: `tests/test_backtest_api.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_backtest_api.py`의 `test_list_strategies` 함수를 아래로 교체한다:

```python
def test_list_strategies(client):
    res = client.get("/api/backtest/strategies")
    assert res.status_code == 200
    data = res.json()
    names = [s["name"] for s in data]
    assert "SMA Crossover" in names
    assert "Equal Weight" in names

    # 모든 전략에 description/icon/tags 필드가 있어야 함
    for s in data:
        assert "description" in s, f"{s['name']} missing description"
        assert "icon" in s, f"{s['name']} missing icon"
        assert "tags" in s, f"{s['name']} missing tags"
        assert isinstance(s["description"], str) and len(s["description"]) > 0
        assert isinstance(s["icon"], str) and len(s["icon"]) > 0
        assert isinstance(s["tags"], list) and len(s["tags"]) > 0
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
pytest tests/test_backtest_api.py::test_list_strategies -v
```

예상 출력: `FAILED` — `KeyError: 'description'` 또는 `AssertionError`

---

## Task 2: 백엔드 — base.py + models.py 업데이트

**Files:**
- Modify: `core/strategies/base.py`
- Modify: `api/models.py`

- [ ] **Step 1: `core/strategies/base.py`에 ClassVar 추가**

`Strategy` 클래스에 세 필드를 추가하고 `list_strategies()`를 업데이트한다:

```python
"""Strategy ABC + Registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from core.engines.portfolio_engine import BacktestContext, BacktestResult


class Strategy(ABC):
    name: ClassVar[str]
    params_schema: ClassVar[dict]       # {"param_name": {"type": "int", "default": 20, "label": "...", "min": 1, "max": 200}}
    engine: ClassVar[str] = "backtesting"       # "backtesting" | "portfolio"
    supports_risk_options: ClassVar[bool] = False
    description: ClassVar[str] = ""
    icon: ClassVar[str] = "📊"
    tags: ClassVar[list[str]] = []

    @abstractmethod
    def to_backtesting_class(self, params: dict):
        """backtesting.py Strategy 클래스를 반환한다."""
        ...

    def run_portfolio(self, ctx: "BacktestContext", params: dict) -> "BacktestResult":
        """portfolio 엔진 전략 실행. engine="portfolio" 전략이 구현한다."""
        raise NotImplementedError(f"{self.name}은 portfolio 엔진을 지원하지 않습니다")


_registry: dict[str, Strategy] = {}


def register(strategy: Strategy):
    _registry[strategy.name] = strategy


def get_strategy(name: str) -> Strategy:
    if name not in _registry:
        raise KeyError(f"전략 없음: {name}")
    return _registry[name]


def list_strategies() -> list[dict]:
    return [
        {
            "name": s.name,
            "params_schema": s.params_schema,
            "engine": s.engine,
            "supports_risk_options": s.supports_risk_options,
            "description": s.description,
            "icon": s.icon,
            "tags": s.tags,
        }
        for s in _registry.values()
    ]
```

- [ ] **Step 2: `api/models.py`의 `StrategiesOut` 업데이트**

`StrategiesOut` 클래스를 찾아 아래로 교체한다:

```python
class StrategiesOut(BaseModel):
    name: str
    params_schema: dict
    engine: str = "backtesting"
    supports_risk_options: bool = False
    description: str = ""
    icon: str = "📊"
    tags: list[str] = []
```

---

## Task 3: 각 전략에 콘텐츠 채우기

**Files:**
- Modify: `core/strategies/sma_crossover.py`
- Modify: `core/strategies/equal_weight.py`
- Modify: `core/strategies/factor_rebalance.py`
- Modify: `core/strategies/hybrid_factor_sma.py`

- [ ] **Step 1: `core/strategies/sma_crossover.py` — SMA Crossover 콘텐츠**

`SMACrossover` 클래스 본문에 세 줄을 추가한다 (`name = "SMA Crossover"` 아래):

```python
class SMACrossover(Strategy):
    name = "SMA Crossover"
    description = "단기·장기 이동평균 골든/데드 크로스로 단일 종목을 매수·매도하는 기술적 추세 전략."
    icon = "📈"
    tags = ["단일종목", "기술적분석", "추세추종"]
    params_schema = {
        "fast": {"type": "int", "default": 5, "label": "단기 SMA", "min": 2, "max": 100},
        "slow": {"type": "int", "default": 20, "label": "장기 SMA", "min": 5, "max": 200},
    }
    # ... 나머지 메서드는 변경 없음
```

- [ ] **Step 2: `core/strategies/equal_weight.py` — Equal Weight 콘텐츠**

`EqualWeight` 클래스 본문에 추가한다 (`name = "Equal Weight"` 아래):

```python
class EqualWeight(Strategy):
    name = "Equal Weight"
    description = "여러 종목에 동일한 비중으로 분산 투자하고 Buy & Hold. 리밸런싱 없이 단순하게 장기 보유."
    icon = "⚖️"
    tags = ["다종목", "초보 친화적", "분산투자"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {}
    # ... 나머지 메서드는 변경 없음
```

- [ ] **Step 3: `core/strategies/factor_rebalance.py` — Forward 팩터 콘텐츠**

`FactorRebalance` 클래스 본문에 추가한다 (`name = "Forward 팩터 리밸런싱"` 아래):

```python
class FactorRebalance(Strategy):
    name = "Forward 팩터 리밸런싱"
    description = "Forward EPS·PER 팩터로 상위 N개 종목을 선별해 매월 말 리밸런싱. Look-ahead bias 있음."
    icon = "🔬"
    tags = ["펀더멘탈", "월 리밸런싱", "팩터투자"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {
        # ... 기존 그대로 유지
```

- [ ] **Step 4: `core/strategies/hybrid_factor_sma.py` — 하이브리드 콘텐츠**

`HybridFactorSMA` 클래스 본문에 추가한다 (`name = "하이브리드 (펀더멘탈+SMA)"` 아래):

```python
class HybridFactorSMA(Strategy):
    name = "하이브리드 (펀더멘탈+SMA)"
    description = "팩터로 후보 종목 선별 후 SMA 골든크로스 종목만 보유. Dead-cross 시 중도 청산."
    icon = "🧬"
    tags = ["고급", "하이브리드", "팩터+기술적"]
    engine = "portfolio"
    supports_risk_options = True
    params_schema: ClassVar[dict] = {
        # ... 기존 그대로 유지
```

---

## Task 4: 테스트 통과 확인 + 커밋

**Files:**
- Test: `tests/test_backtest_api.py`

- [ ] **Step 1: 테스트 실행 → 통과 확인**

```bash
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
pytest tests/test_backtest_api.py -v
```

예상 출력: `PASSED` — 모든 테스트 통과

- [ ] **Step 2: 백엔드 커밋**

```bash
git add core/strategies/base.py core/strategies/sma_crossover.py \
        core/strategies/equal_weight.py core/strategies/factor_rebalance.py \
        core/strategies/hybrid_factor_sma.py api/models.py \
        tests/test_backtest_api.py
git commit -m "feat: 전략 description/icon/tags API 추가"
```

---

## Task 5: 프론트엔드 타입 업데이트

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: `StrategyDef` 인터페이스에 Optional 필드 추가**

`frontend/lib/types.ts`의 `StrategyDef` 인터페이스를 찾아 아래로 교체한다:

```typescript
export interface StrategyDef {
  name: string;
  params_schema: Record<string, {
    type: string;
    default: number;
    label: string;
    min?: number;
    max?: number;
    options?: string[];
  }>;
  engine: string;
  supports_risk_options: boolean;
  description?: string;
  icon?: string;
  tags?: string[];
}
```

---

## Task 6: 프론트엔드 UI — 드롭다운 + 카드

**Files:**
- Modify: `frontend/components/backtest/backtest-form.tsx`

- [ ] **Step 1: 드롭다운 아이템 렌더링 업데이트**

`backtest-form.tsx`의 전략 `Select` 컴포넌트 내부 `SelectItem` 부분을 찾아 교체한다.

기존:
```tsx
{strategies?.map((s) => (
  <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>
))}
```

교체:
```tsx
{strategies?.map((s) => (
  <SelectItem key={s.name} value={s.name}>
    <div className="flex items-center gap-2 py-0.5">
      {s.icon && <span className="text-base leading-none">{s.icon}</span>}
      <div className="flex flex-col">
        <span className="text-[13px] font-medium">{s.name}</span>
        {s.description && (
          <span className="text-[11px] text-muted-foreground leading-tight">{s.description}</span>
        )}
      </div>
      {s.tags?.[0] && (
        <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground shrink-0">
          {s.tags[0]}
        </span>
      )}
    </div>
  </SelectItem>
))}
```

- [ ] **Step 2: 선택 후 설명 카드 추가**

파라미터 설정 `<div className="grid ...">` 블록 아래, `{selectedStrategy && Object.keys(...)...}` 블록 위에 다음을 추가한다:

```tsx
{selectedStrategy?.description && (
  <div className="rounded-lg border bg-muted/30 p-3 flex items-start gap-3">
    {selectedStrategy.icon && (
      <span className="text-2xl leading-none mt-0.5">{selectedStrategy.icon}</span>
    )}
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[13px] font-semibold">{selectedStrategy.name}</span>
        {selectedStrategy.tags?.map((tag) => (
          <span
            key={tag}
            className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary"
          >
            {tag}
          </span>
        ))}
      </div>
      <p className="text-[12px] text-muted-foreground leading-relaxed">
        {selectedStrategy.description}
      </p>
    </div>
  </div>
)}
```

- [ ] **Step 3: TypeScript 타입 체크**

```bash
cd /Users/user/Development/private/dudunomics/frontend
npx tsc --noEmit
```

예상 출력: 에러 없음

- [ ] **Step 4: 프론트엔드 커밋**

```bash
cd /Users/user/Development/private/dudunomics
git add frontend/lib/types.ts frontend/components/backtest/backtest-form.tsx
git commit -m "feat: 전략 설명 아이콘·카드 UI 추가 (A+B 조합)"
```

---

## Task 7: 시각 검증 (gstack-browse)

**Files:** 없음 (검증만)

- [ ] **Step 1: 개발 서버 + 백엔드 시작**

```bash
# 터미널 1: 백엔드
cd /Users/user/Development/private/dudunomics
source .venv/bin/activate
uvicorn api.main:app --port 8000 &

# 터미널 2: 프론트엔드
cd /Users/user/Development/private/dudunomics/frontend
npm run dev -- --port 3333 &
```

- [ ] **Step 2: gstack-browse로 /backtest 확인**

`gstack-browse` 스킬로 `http://localhost:3333/backtest` 접속 후:
1. 전략 드롭다운 열면 → 각 항목에 이모지 + 1줄 설명 + 태그 배지 보임
2. 전략 선택 후 → 드롭다운 아래에 설명 카드 확장됨
3. 다른 전략으로 변경 → 카드 내용이 바뀜

---

## 완료 기준

- [ ] `pytest tests/test_backtest_api.py -v` — 전체 통과
- [ ] `/api/backtest/strategies` 응답에 모든 전략의 `description`/`icon`/`tags` 포함
- [ ] 드롭다운 아이템에 이모지 + 요약 + 태그 배지 표시
- [ ] 전략 선택 시 설명 카드 확장
- [ ] `tsc --noEmit` 에러 없음
