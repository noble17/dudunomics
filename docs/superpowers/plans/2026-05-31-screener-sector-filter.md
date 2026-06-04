# Screener Sector/Industry Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스크리너 사이드바에 섹터/인더스트리 2단계 필터를 추가하고, 의미 없는 CFO 하드 필터를 제거한다.

**Architecture:** 클라이언트 사이드 필터링 전용 (API 변경 없음). scores 배열에서 섹터/인더스트리 목록을 동적 추출하여 드롭다운에 바인딩. 섹터 변경 시 인더스트리 자동 리셋.

**Tech Stack:** Next.js (App Router), React, TypeScript, Tailwind CSS

---

## 변경 파일 맵

| 파일 | 역할 |
|---|---|
| `frontend/lib/types.ts` | `QuantScore`에 sector/industry 추가, hardFilters 타입에서 cfo 제거 |
| `frontend/components/screener/ranking-table.tsx` | CFO 필터 로직 제거, 섹터/인더스트리 필터 추가 |
| `frontend/components/screener/factor-sidebar.tsx` | CFO 체크박스 제거, 섹터/인더스트리 셀렉트 추가 |
| `frontend/app/screener/page.tsx` | state/useMemo 추가, props 연결, CFO 잔재 제거 |

---

### Task 1: types.ts — QuantScore에 sector/industry 추가, hardFilters에서 cfo 제거

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: QuantScore 인터페이스에 필드 추가**

`frontend/lib/types.ts`의 `QuantScore` 인터페이스 (133번째 줄 부근) 끝에 두 필드를 추가한다:

```typescript
export interface QuantScore {
  ticker: string;
  universe: string;
  as_of: string;
  company_name: string | null;
  pct_momentum: number | null;
  pct_valuation: number | null;
  pct_eps_momentum: number | null;
  pct_quality: number | null;
  pct_technical: number | null;
  raw_momentum: number | null;
  raw_fwd_pe: number | null;
  raw_pbr: number | null;
  raw_psr: number | null;
  raw_trailing_pe: number | null;
  raw_eps_ttm: number | null;
  raw_fwd_eps: number | null;
  raw_roe: number | null;
  raw_debt_ratio: number | null;
  raw_rsi: number | null;
  above_ma200: boolean | null;
  cfo_positive: boolean | null;
  sector: string | null;
  industry: string | null;
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/lib/types.ts
git commit -m "feat(screener): add sector/industry fields to QuantScore type"
```

---

### Task 2: ranking-table.tsx — CFO 필터 제거, 섹터/인더스트리 필터 추가

**Files:**
- Modify: `frontend/components/screener/ranking-table.tsx`

- [ ] **Step 1: Props 인터페이스 수정**

기존:
```typescript
interface Props {
  scores: QuantScore[];
  weights: FactorWeights;
  hardFilters: { ma200: boolean; cfo: boolean };
  topN?: number;
  universe?: string;
  isBatchRunning?: boolean;
}
```

변경 후:
```typescript
interface Props {
  scores: QuantScore[];
  weights: FactorWeights;
  hardFilters: { ma200: boolean };
  sectorFilter: string;
  industryFilter: string;
  topN?: number;
  universe?: string;
  isBatchRunning?: boolean;
}
```

- [ ] **Step 2: 함수 시그니처 및 필터 로직 수정**

기존 `RankingTable` 함수 선언부와 `filtered` 계산 부분:
```typescript
export function RankingTable({ scores, weights, hardFilters, topN = 50, universe = "sp500", isBatchRunning = false }: Props) {
  const router = useRouter();
  const norm = normalizeWeights(weights);

  const filtered = scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (hardFilters.cfo  && s.cfo_positive === false) return false;
    return true;
  });
```

변경 후:
```typescript
export function RankingTable({ scores, weights, hardFilters, sectorFilter, industryFilter, topN = 50, universe = "sp500", isBatchRunning = false }: Props) {
  const router = useRouter();
  const norm = normalizeWeights(weights);

  const filtered = scores.filter((s) => {
    if (hardFilters.ma200 && s.above_ma200 === false) return false;
    if (sectorFilter && s.sector !== sectorFilter) return false;
    if (industryFilter && s.industry !== industryFilter) return false;
    return true;
  });
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/screener/ranking-table.tsx
git commit -m "feat(screener): replace cfo filter with sector/industry filter in ranking table"
```

---

### Task 3: factor-sidebar.tsx — CFO 체크박스 제거, 섹터/인더스트리 셀렉트 추가

**Files:**
- Modify: `frontend/components/screener/factor-sidebar.tsx`

- [ ] **Step 1: Props 인터페이스 수정**

기존:
```typescript
interface Props {
  universe: string;
  onUniverseChange: (u: string) => void;
  weights: FactorWeights;
  onWeightsChange: (w: FactorWeights) => void;
  hardFilters: { ma200: boolean; cfo: boolean };
  onHardFiltersChange: (f: { ma200: boolean; cfo: boolean }) => void;
  totalCount: number;
  filteredCount: number;
}
```

변경 후:
```typescript
interface Props {
  universe: string;
  onUniverseChange: (u: string) => void;
  weights: FactorWeights;
  onWeightsChange: (w: FactorWeights) => void;
  hardFilters: { ma200: boolean };
  onHardFiltersChange: (f: { ma200: boolean }) => void;
  sectorFilter: string;
  onSectorChange: (s: string) => void;
  industryFilter: string;
  onIndustryChange: (i: string) => void;
  sectors: string[];
  industries: string[];
  totalCount: number;
  filteredCount: number;
}
```

- [ ] **Step 2: 함수 시그니처 수정**

기존:
```typescript
export function FactorSidebar({
  universe, onUniverseChange,
  weights, onWeightsChange,
  hardFilters, onHardFiltersChange,
  totalCount, filteredCount,
}: Props) {
```

변경 후:
```typescript
export function FactorSidebar({
  universe, onUniverseChange,
  weights, onWeightsChange,
  hardFilters, onHardFiltersChange,
  sectorFilter, onSectorChange,
  industryFilter, onIndustryChange,
  sectors, industries,
  totalCount, filteredCount,
}: Props) {
```

- [ ] **Step 3: 하드 필터 섹션에서 CFO 체크박스 제거**

기존 하드 필터 섹션:
```tsx
{/* 하드 필터 */}
<div>
  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">하드 필터</p>
  <label className="flex items-center gap-2 text-sm cursor-pointer mb-1">
    <input
      type="checkbox"
      checked={hardFilters.ma200}
      onChange={(e) => onHardFiltersChange({ ...hardFilters, ma200: e.target.checked })}
    />
    200일 MA 하회 제외
  </label>
  <label className="flex items-center gap-2 text-sm cursor-pointer">
    <input
      type="checkbox"
      checked={hardFilters.cfo}
      onChange={(e) => onHardFiltersChange({ ...hardFilters, cfo: e.target.checked })}
    />
    CFO 음수 제외
  </label>
</div>
```

변경 후:
```tsx
{/* 하드 필터 */}
<div>
  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">하드 필터</p>
  <label className="flex items-center gap-2 text-sm cursor-pointer">
    <input
      type="checkbox"
      checked={hardFilters.ma200}
      onChange={(e) => onHardFiltersChange({ ma200: e.target.checked })}
    />
    200일 MA 하회 제외
  </label>
</div>
```

- [ ] **Step 4: 섹터/인더스트리 섹션 추가 (하드 필터 아래, 결과 요약 위)**

결과 요약 `<p>` 태그 바로 위에 삽입:
```tsx
{/* 섹터 / 인더스트리 */}
<div>
  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">섹터 / 인더스트리</p>
  <select
    value={sectorFilter}
    onChange={(e) => onSectorChange(e.target.value)}
    className="w-full rounded border border-border bg-muted px-2 py-1 text-sm mb-2"
  >
    <option value="">전체 섹터</option>
    {sectors.map((s) => (
      <option key={s} value={s}>{s}</option>
    ))}
  </select>
  <select
    value={industryFilter}
    onChange={(e) => onIndustryChange(e.target.value)}
    disabled={!sectorFilter}
    className="w-full rounded border border-border bg-muted px-2 py-1 text-sm disabled:opacity-40"
  >
    <option value="">전체 인더스트리</option>
    {industries.map((i) => (
      <option key={i} value={i}>{i}</option>
    ))}
  </select>
</div>
```

- [ ] **Step 5: 커밋**

```bash
git add frontend/components/screener/factor-sidebar.tsx
git commit -m "feat(screener): add sector/industry selects, remove cfo checkbox"
```

---

### Task 4: screener/page.tsx — state/useMemo 추가, props 연결, CFO 잔재 제거

**Files:**
- Modify: `frontend/app/screener/page.tsx`

- [ ] **Step 1: hardFilters 초기값에서 cfo 제거**

기존:
```typescript
const [hardFilters, setHardFilters] = useState({ ma200: true, cfo: true });
```

변경 후:
```typescript
const [hardFilters, setHardFilters] = useState({ ma200: true });
```

- [ ] **Step 2: handleUniverseChange에서 cfo 제거**

기존:
```typescript
const handleUniverseChange = (u: string) => {
  setUniverse(u);
  if (DOMESTIC.includes(u)) setHardFilters({ ma200: false, cfo: false });
  else setHardFilters({ ma200: true, cfo: true });
};
```

변경 후:
```typescript
const handleUniverseChange = (u: string) => {
  setUniverse(u);
  if (DOMESTIC.includes(u)) setHardFilters({ ma200: false });
  else setHardFilters({ ma200: true });
};
```

- [ ] **Step 3: sectorFilter/industryFilter state 추가**

`hardFilters` state 선언 아래에 추가:
```typescript
const [sectorFilter, setSectorFilter] = useState("");
const [industryFilter, setIndustryFilter] = useState("");
```

- [ ] **Step 4: sectors/industries useMemo 추가**

`filteredCount` useMemo 위에 추가:
```typescript
const sectors = useMemo(
  () => [...new Set(scores.map((s) => s.sector).filter((s): s is string => !!s))].sort(),
  [scores]
);

const industries = useMemo(
  () =>
    sectorFilter
      ? [...new Set(
          scores
            .filter((s) => s.sector === sectorFilter)
            .map((s) => s.industry)
            .filter((i): i is string => !!i)
        )].sort()
      : [],
  [scores, sectorFilter]
);

const handleSectorChange = (s: string) => {
  setSectorFilter(s);
  setIndustryFilter("");
};
```

- [ ] **Step 5: filteredCount useMemo에 섹터/인더스트리 필터 추가, cfo 제거**

기존:
```typescript
const filteredCount = useMemo(() => scores.filter((s) => {
  if (hardFilters.ma200 && s.above_ma200 === false) return false;
  if (hardFilters.cfo  && s.cfo_positive === false) return false;
  return true;
}).length, [scores, hardFilters]);
```

변경 후:
```typescript
const filteredCount = useMemo(() => scores.filter((s) => {
  if (hardFilters.ma200 && s.above_ma200 === false) return false;
  if (sectorFilter && s.sector !== sectorFilter) return false;
  if (industryFilter && s.industry !== industryFilter) return false;
  return true;
}).length, [scores, hardFilters, sectorFilter, industryFilter]);
```

- [ ] **Step 6: 도움말 텍스트에서 CFO 언급 제거**

기존:
```tsx
<div className="rounded border border-border bg-background px-3 py-2">
  <p className="font-medium text-foreground text-xs mb-0.5">하드 필터</p>
  <p className="text-muted-foreground text-xs">200일 MA 하회 · CFO 음수 종목을 랭킹에서 완전 제외. 체크 해제 시 포함.</p>
</div>
```

변경 후:
```tsx
<div className="rounded border border-border bg-background px-3 py-2">
  <p className="font-medium text-foreground text-xs mb-0.5">하드 필터</p>
  <p className="text-muted-foreground text-xs">200일 MA 하회 종목을 랭킹에서 완전 제외. 체크 해제 시 포함.</p>
</div>
```

- [ ] **Step 7: FactorSidebar props에 새 props 전달**

기존:
```tsx
<FactorSidebar
  universe={universe}
  onUniverseChange={handleUniverseChange}
  weights={weights}
  onWeightsChange={setWeights}
  hardFilters={hardFilters}
  onHardFiltersChange={setHardFilters}
  totalCount={scores.length}
  filteredCount={filteredCount}
/>
```

변경 후:
```tsx
<FactorSidebar
  universe={universe}
  onUniverseChange={handleUniverseChange}
  weights={weights}
  onWeightsChange={setWeights}
  hardFilters={hardFilters}
  onHardFiltersChange={setHardFilters}
  sectorFilter={sectorFilter}
  onSectorChange={handleSectorChange}
  industryFilter={industryFilter}
  onIndustryChange={setIndustryFilter}
  sectors={sectors}
  industries={industries}
  totalCount={scores.length}
  filteredCount={filteredCount}
/>
```

- [ ] **Step 8: RankingTable props에 새 props 전달**

기존:
```tsx
<RankingTable
  scores={scores}
  weights={weights}
  hardFilters={hardFilters}
  topN={50}
  universe={universe}
  isBatchRunning={refreshing}
/>
```

변경 후:
```tsx
<RankingTable
  scores={scores}
  weights={weights}
  hardFilters={hardFilters}
  sectorFilter={sectorFilter}
  industryFilter={industryFilter}
  topN={50}
  universe={universe}
  isBatchRunning={refreshing}
/>
```

- [ ] **Step 9: 커밋**

```bash
git add frontend/app/screener/page.tsx
git commit -m "feat(screener): wire sector/industry filter state and remove cfo filter"
```

---

### Task 5: 브라우저 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 프론트엔드 서버 확인 후 스크리너 페이지 열기**

```bash
# 프론트엔드가 실행 중인지 확인 (보통 3000번 포트)
curl -s http://localhost:3000/screener | head -5
```

- [ ] **Step 2: gstack-browse 또는 브라우저로 다음 시나리오 검증**

1. `/screener` 페이지 진입 → 사이드바에 "섹터 / 인더스트리" 섹션 표시 확인
2. CFO 체크박스가 없어졌는지 확인
3. 섹터 드롭다운에서 "Technology" 선택 → 테이블이 Technology 종목만 표시 확인
4. 인더스트리 드롭다운 활성화 → "Semiconductors" 선택 → 테이블 추가 필터링 확인
5. 섹터를 "전체 섹터"로 변경 → 인더스트리 드롭다운 disabled + 전체 종목 표시 확인
6. 섹터 변경 시 인더스트리가 "전체 인더스트리"로 자동 리셋되는지 확인
7. 결과 요약 `N / 503개 종목`이 필터에 맞게 업데이트되는지 확인

- [ ] **Step 3: TypeScript 오류 없음 확인**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 오류 없음
