# M4 Bloomberg Terminal UI 재설계 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/terminal` 페이지를 Bloomberg 다크 테마 + 5탭 내비게이션 + Market Overview + 드래그 리사이즈 패널로 전면 재설계한다.

**Architecture:** `.terminal-dark` CSS 스코프로 Bloomberg 색상 변수를 격리하고, URL query param(`?tab=markets`)으로 탭 상태를 관리한다. `react-resizable-panels@4` (`Group`+`Panel`+`Separator` 네이밍)로 MarketsPanel의 Row 2를 3분할 드래그 패널로 구현한다. 기존 Widget 컴포넌트(Watchlist, Portfolio, Screener, Backtest)는 새 패널들 내부에서 그대로 재활용한다.

**Tech Stack:** Next.js 15 App Router, React 19, `react-resizable-panels@4.11` (`Group`/`Separator` exports), `swr`, Tailwind v4, `useSearchParams` + `Suspense` (Next.js 필수 래핑)

---

## File Structure

| 파일 | 변경 |
|---|---|
| `frontend/app/globals.css` | `.terminal-dark` CSS 변수 블록 추가 |
| `frontend/app/terminal/page.tsx` | Shell → TabShell 교체, outer div에 `terminal-dark` 클래스 추가 |
| `frontend/components/terminal/GlobalNav.tsx` | Bloomberg 5탭 내비로 전면 교체 |
| `frontend/components/terminal/IndexStrip.tsx` | INDICES 레이블 + EST 시각 추가 |
| `frontend/components/terminal/Shell.tsx` | **삭제** (TabShell로 대체) |
| `frontend/components/terminal/TabShell.tsx` | **신규** — URL-based 탭 라우팅 |
| `frontend/components/terminal/panels/AiPanel.tsx` | **신규** — placeholder |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | **신규** — 3-row 레이아웃 |
| `frontend/components/terminal/panels/PortfolioPanel.tsx` | **신규** — 3분할 Bloomberg 스타일 |
| `frontend/components/terminal/panels/ResearchPanel.tsx` | **신규** — ScreenerWidget 래퍼 |
| `frontend/components/terminal/panels/ToolsPanel.tsx` | **신규** — BacktestWidget 래퍼 |

---

## Task 1: Bloomberg 다크 테마 CSS 변수

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: globals.css 끝에 `.terminal-dark` 스코프 변수 블록 추가**

파일 끝(`@utility border-t-fall ...` 다음)에 아래를 추가한다:

```css
/* Bloomberg Terminal 다크 테마 — /terminal 페이지 전용 스코프 */
.terminal-dark {
  --color-bg-primary:    #0a0a0a;
  --color-bg-secondary:  #0f0f0f;
  --color-bg-tertiary:   #141414;
  --color-border:        #1a1a1a;
  --color-border-subtle: #111111;
  --color-text-primary:  #ffffff;
  --color-text-secondary: #888888;
  --color-text-muted:    #444444;
  --color-primary:       #ff6600;
  --color-primary-dim:   #cc5200;
  --color-gain:          #ff4444;
  --color-loss:          #4488ff;
  --color-connected:     #44aa44;
  --color-placeholder:   #333333;
}
```

- [ ] **Step 2: TypeScript/CSS 오류 없음 확인**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음 (CSS 전용 변경이므로 tsc는 항상 패스)

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat(terminal/m4): add .terminal-dark Bloomberg CSS variable scope"
```

---

## Task 2: AiPanel, ResearchPanel, ToolsPanel 신규 (단순 래퍼 3개)

**Files:**
- Create: `frontend/components/terminal/panels/AiPanel.tsx`
- Create: `frontend/components/terminal/panels/ResearchPanel.tsx`
- Create: `frontend/components/terminal/panels/ToolsPanel.tsx`

- [ ] **Step 1: panels/ 디렉토리 확인**

```bash
ls frontend/components/terminal/
```
Expected: `panels/` 디렉토리가 없으면 파일 생성 시 자동 생성됨 (Write 툴이 처리)

- [ ] **Step 2: AiPanel.tsx 작성**

```tsx
export function AiPanel() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4">
      <div className="text-center">
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">
          AI ASSISTANT
        </p>
        <p className="text-xs font-mono text-[var(--color-text-muted)]">
          Gemini API — M6에서 연결 예정
        </p>
      </div>
      <button
        disabled
        className="text-xs font-mono text-[var(--color-text-muted)] border border-[var(--color-placeholder)] rounded px-4 py-2 cursor-not-allowed opacity-50"
      >
        API 키 설정
      </button>
    </div>
  );
}
```

- [ ] **Step 3: ResearchPanel.tsx 작성**

```tsx
import { ScreenerWidget } from "@/components/terminal/widgets/Screener";

export function ResearchPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        RESEARCH — QUANT SCREENER
      </div>
      <div className="flex-1 overflow-auto p-4">
        <ScreenerWidget />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: ToolsPanel.tsx 작성**

```tsx
import { BacktestWidget } from "@/components/terminal/widgets/Backtest";

export function ToolsPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        TOOLS — BACKTEST
      </div>
      <div className="flex-1 overflow-auto p-4">
        <BacktestWidget />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 6: Commit**

```bash
git add frontend/components/terminal/panels/AiPanel.tsx \
        frontend/components/terminal/panels/ResearchPanel.tsx \
        frontend/components/terminal/panels/ToolsPanel.tsx
git commit -m "feat(terminal/m4): add AiPanel, ResearchPanel, ToolsPanel wrappers"
```

---

## Task 3: TabShell.tsx 신규 (URL-based 탭 라우팅)

**Files:**
- Create: `frontend/components/terminal/TabShell.tsx`

`useSearchParams`는 Next.js에서 반드시 `<Suspense>`로 감싸야 한다.

- [ ] **Step 1: TabShell.tsx 작성**

```tsx
"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { MarketsPanel } from "./panels/MarketsPanel";
import { PortfolioPanel } from "./panels/PortfolioPanel";
import { ResearchPanel } from "./panels/ResearchPanel";
import { ToolsPanel } from "./panels/ToolsPanel";
import { AiPanel } from "./panels/AiPanel";

type TabKey = "markets" | "portfolio" | "research" | "tools" | "ai";
const VALID_TABS: TabKey[] = ["markets", "portfolio", "research", "tools", "ai"];

function TabShellInner() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("tab") ?? "markets";
  const tab: TabKey = VALID_TABS.includes(raw as TabKey) ? (raw as TabKey) : "markets";

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {tab === "markets"   && <MarketsPanel />}
      {tab === "portfolio" && <PortfolioPanel />}
      {tab === "research"  && <ResearchPanel />}
      {tab === "tools"     && <ToolsPanel />}
      {tab === "ai"        && <AiPanel />}
    </div>
  );
}

export function TabShell() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-secondary)]">
        로딩 중…
      </div>
    }>
      <TabShellInner />
    </Suspense>
  );
}
```

- [ ] **Step 2: TypeScript 체크**

MarketsPanel/PortfolioPanel은 아직 없으므로 에러가 나면 임시로 각 import를 주석 처리하고 나중 태스크에서 복원한다. 대신 아래처럼 stub을 먼저 만들어도 된다.

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

MarketsPanel/PortfolioPanel 미존재로 인한 에러만 허용. 나머지 에러는 수정.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/TabShell.tsx
git commit -m "feat(terminal/m4): add TabShell with URL query param tab routing"
```

---

## Task 4: GlobalNav.tsx 교체 (Bloomberg 5탭)

**Files:**
- Modify: `frontend/components/terminal/GlobalNav.tsx`

`useSearchParams` 사용 → `<Suspense>` 필수.

- [ ] **Step 1: GlobalNav.tsx 전체 교체**

```tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useCommandStore } from "@/lib/stores/command";
import { UserMenu } from "@/components/user-menu";
import useSWR from "swr";

type TabKey = "markets" | "portfolio" | "research" | "tools" | "ai";

const TABS: { key: TabKey; label: string }[] = [
  { key: "markets",   label: "MARKETS" },
  { key: "portfolio", label: "PORTFOLIO" },
  { key: "research",  label: "RESEARCH" },
  { key: "tools",     label: "TOOLS" },
  { key: "ai",        label: "AI" },
];

function useMe() {
  return useSWR("/api/auth/me", () =>
    fetch("/api/auth/me", { credentials: "include" }).then(r => r.ok ? r.json() : null)
  );
}

function GlobalNavInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const openPalette = useCommandStore(s => s.openPalette);
  const { data: me } = useMe();
  const activeTab = searchParams.get("tab") ?? "markets";

  function switchTab(key: TabKey) {
    router.push(`/terminal?tab=${key}`);
  }

  return (
    <div className="flex items-center justify-between px-4 h-10 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      <div className="flex items-center h-full">
        <span className="font-mono text-sm font-bold text-[var(--color-primary)] mr-6 shrink-0">
          Dudunomics
        </span>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => switchTab(tab.key)}
            className={[
              "h-full px-4 text-[11px] font-mono tracking-wider transition-colors shrink-0",
              activeTab === tab.key
                ? "border-t-2 border-[var(--color-primary)] bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={openPalette}
          className="flex items-center gap-2 text-[11px] font-mono text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded px-3 py-1 hover:border-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <span>LLM &lt;GO&gt;</span>
          <kbd className="text-[10px] bg-[var(--color-bg-primary)] px-1 rounded">⌘K</kbd>
        </button>
        <button
          disabled
          className="text-[11px] font-mono text-[var(--color-text-muted)] border border-[var(--color-border)] rounded px-3 py-1 cursor-not-allowed opacity-40"
        >
          AI COPILOT
        </button>
        {me?.email && <UserMenu email={me.email} />}
      </div>
    </div>
  );
}

export function GlobalNav() {
  return (
    <Suspense fallback={
      <div className="h-10 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)] shrink-0" />
    }>
      <GlobalNavInner />
    </Suspense>
  );
}
```

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/GlobalNav.tsx
git commit -m "feat(terminal/m4): replace GlobalNav with Bloomberg 5-tab navigation"
```

---

## Task 5: MarketsPanel — Row 1 (Market Overview 타일 8개)

**Files:**
- Create: `frontend/components/terminal/panels/MarketsPanel.tsx`

이 태스크에서는 Row 1만 구현하고 Row 2/Row 3는 빈 div placeholder로 남긴다. 이후 태스크에서 채운다.

- [ ] **Step 1: MarketsPanel.tsx 작성 (Row 1 + placeholder Row 2/3)**

react-resizable-panels 및 portfolioApi는 Task 6/7에서 추가한다. 이 태스크에서는 Row 1 타일에만 집중.

```tsx
"use client";
import useSWR from "swr";
import { quotesApi } from "@/lib/api";
import type { QuotesOut } from "@/lib/types";

type TileConfig = {
  label: string;
  quoteKey: keyof QuotesOut | null;
  decimals: number;
};

const TILES: TileConfig[] = [
  { label: "SPY",     quoteKey: "SPY",  decimals: 2 },
  { label: "QQQ",     quoteKey: "QQQ",  decimals: 2 },
  { label: "DJI",     quoteKey: null,   decimals: 0 },
  { label: "VIX",     quoteKey: null,   decimals: 2 },
  { label: "US10Y",   quoteKey: null,   decimals: 2 },
  { label: "WTI",     quoteKey: null,   decimals: 2 },
  { label: "GOLD",    quoteKey: null,   decimals: 0 },
  { label: "BTC/USD", quoteKey: "BTC",  decimals: 0 },
];

function fmt(value: number, decimals: number): string {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function MarketTile({ config, quotes }: { config: TileConfig; quotes: QuotesOut | null }) {
  const item = config.quoteKey ? quotes?.[config.quoteKey] : null;
  const up   = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;

  return (
    <div className="flex flex-col justify-center px-3 border-r border-[var(--color-border)] shrink-0 min-w-[88px]">
      <span className="text-[9px] font-mono uppercase tracking-wider text-[var(--color-text-secondary)]">
        {config.label}
      </span>
      {item ? (
        <>
          <span className="text-[11px] font-mono text-[var(--color-text-primary)] leading-tight">
            {fmt(item.price, config.decimals)}
          </span>
          <span
            className={[
              "text-[10px] font-mono leading-tight",
              up   ? "text-[var(--color-gain)]" :
              down ? "text-[var(--color-loss)]" :
                     "text-[var(--color-text-muted)]",
            ].join(" ")}
          >
            {up ? "▲" : down ? "▼" : ""}
            {item.change_pct >= 0 ? "+" : ""}
            {item.change_pct.toFixed(2)}%
          </span>
        </>
      ) : (
        <>
          <span className="text-[11px] font-mono text-[var(--color-text-muted)]">—</span>
          {config.quoteKey === null && (
            <span className="text-[9px] font-mono text-[var(--color-placeholder)]">API 필요</span>
          )}
        </>
      )}
    </div>
  );
}

export function MarketsPanel() {
  const { data: quotes } = useSWR("/api/quotes", quotesApi.get, { refreshInterval: 10_000 });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Row 1: Market Overview 타일 (height: 80px) */}
      <div className="h-20 shrink-0 flex items-stretch border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="flex items-stretch flex-1 overflow-x-auto">
          {TILES.map(tile => (
            <MarketTile key={tile.label} config={tile} quotes={quotes ?? null} />
          ))}
        </div>
      </div>

      {/* Row 2: 3분할 패널 placeholder — Task 6에서 구현 */}
      <div className="flex-1 overflow-hidden flex items-center justify-center text-xs font-mono text-[var(--color-text-muted)]">
        Row 2 — Task 6에서 구현
      </div>

      {/* Row 3: 포트폴리오 요약 placeholder — Task 7에서 구현 */}
      <div className="h-18 shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]" />
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/panels/MarketsPanel.tsx
git commit -m "feat(terminal/m4): add MarketsPanel Row 1 market overview tiles"
```

---

## Task 6: MarketsPanel — Row 2 (3분할 드래그 패널)

**Files:**
- Modify: `frontend/components/terminal/panels/MarketsPanel.tsx`

Row 2 placeholder를 실제 `react-resizable-panels` 3분할 패널로 교체한다. 사용 패턴은 `Shell.tsx`와 동일 (`Group`, `Panel`, `Separator` imports).

먼저 파일 상단 import에 아래 2줄을 추가한다:
```tsx
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { WatchlistWidget } from "@/components/terminal/widgets/Watchlist";
```

그리고 `MarketsPanel` 함수 바깥에 `ResizeHandle` 컴포넌트를 추가한다:
```tsx
function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}
```

- [ ] **Step 1: MarketsPanel.tsx의 Row 2 placeholder를 아래로 교체**

`{/* Row 2: 3분할 패널 placeholder — Task 6에서 구현 */}` 블록 전체를:

```tsx
      {/* Row 2: 3분할 드래그 패널 */}
      <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
        {/* 좌: Watchlist (기본 20%) */}
        <Panel defaultSize={20} minSize={12} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            WATCHLIST
          </div>
          <div className="flex-1 overflow-auto p-2">
            <WatchlistWidget />
          </div>
        </Panel>

        <ResizeHandle />

        {/* 중: Chart placeholder (기본 50%) */}
        <Panel defaultSize={50} minSize={20} className="flex flex-col overflow-hidden border-x border-[var(--color-border)]">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            CHART
          </div>
          <div className="flex-1 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">
              캔들 차트 — M5에서 연결
            </span>
          </div>
        </Panel>

        <ResizeHandle />

        {/* 우: Top News placeholder (기본 30%) */}
        <Panel defaultSize={30} minSize={12} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
            TOP NEWS
          </div>
          <div className="flex-1 flex items-center justify-center">
            <span className="text-xs font-mono text-[var(--color-text-muted)]">
              뉴스 — M6에서 연결
            </span>
          </div>
        </Panel>
      </PanelGroup>
```

으로 교체.

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/panels/MarketsPanel.tsx
git commit -m "feat(terminal/m4): add MarketsPanel Row 2 three-column resizable panels"
```

---

## Task 7: MarketsPanel — Row 3 (포트폴리오 요약 + AI placeholder)

**Files:**
- Modify: `frontend/components/terminal/panels/MarketsPanel.tsx`

Row 3 placeholder를 실제 포트폴리오 요약으로 교체한다.

`PortfolioSnapshot`에는 오늘 손익 필드가 없으므로 총 평가액만 표시하고 나머지는 "—"로 처리한다 (절대 가짜 숫자 금지).

먼저 파일 상단 import를 다음으로 업데이트:
```tsx
import { quotesApi, portfolioApi } from "@/lib/api";
```

그리고 `MarketsPanel` 함수 내부에 snapshot 패치를 추가:
```tsx
const { data: snapshot } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });
```

- [ ] **Step 1: MarketsPanel.tsx의 Row 3 placeholder를 아래로 교체**

`{/* Row 3: 포트폴리오 요약 placeholder — Task 7에서 구현 */}` 블록 전체를:

```tsx
      {/* Row 3: 포트폴리오 요약 + AI (height: 72px) */}
      <div className="h-[72px] shrink-0 flex border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        {/* 좌 (50%): MY PORTFOLIO */}
        <div className="flex-1 flex flex-col justify-center px-4 border-r border-[var(--color-border)]">
          <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-1">
            MY PORTFOLIO
          </p>
          {snapshot ? (
            <div className="flex items-baseline gap-4">
              <span className="text-[13px] font-mono text-[var(--color-text-primary)]">
                ₩{snapshot.total_with_cash_krw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
              </span>
              <span className="text-[10px] font-mono text-[var(--color-text-secondary)]">
                오늘 손익 <span className="text-[var(--color-text-muted)]">—</span>
              </span>
            </div>
          ) : (
            <span className="text-[11px] font-mono text-[var(--color-text-muted)]">로딩 중…</span>
          )}
        </div>
        {/* 우 (50%): AI ASSISTANT placeholder */}
        <div className="flex-1 flex flex-col justify-center px-4">
          <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-1">
            AI ASSISTANT
          </p>
          <span className="text-[11px] font-mono text-[var(--color-text-muted)]">
            Gemini API — M6에서 연결
          </span>
        </div>
      </div>
```

으로 교체.

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/panels/MarketsPanel.tsx
git commit -m "feat(terminal/m4): add MarketsPanel Row 3 portfolio summary"
```

---

## Task 8: PortfolioPanel.tsx 신규 (3분할 Bloomberg 스타일)

**Files:**
- Create: `frontend/components/terminal/panels/PortfolioPanel.tsx`

3분할: 좌(25%) WatchlistWidget | 중(50%) PortfolioWidget | 우(25%) 섹터/통화 비중

- [ ] **Step 1: PortfolioPanel.tsx 작성**

```tsx
"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { WatchlistWidget } from "@/components/terminal/widgets/Watchlist";
import { PortfolioWidget } from "@/components/terminal/widgets/Portfolio";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

function BreakdownPanel() {
  const { data: snapshot } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });

  if (!snapshot?.rows.length) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-muted)]">
        데이터 없음
      </div>
    );
  }

  // 통화별 비중 집계
  const currencyMap: Record<string, number> = {};
  for (const row of snapshot.rows) {
    currencyMap[row.currency] = (currencyMap[row.currency] ?? 0) + row.market_value_krw;
  }
  const total = snapshot.total_equity_krw || 1;
  const currencies = Object.entries(currencyMap).sort((a, b) => b[1] - a[1]);

  // 섹터별 비중 집계
  const sectorMap: Record<string, number> = {};
  for (const row of snapshot.rows) {
    const key = row.sector ?? "기타";
    sectorMap[key] = (sectorMap[key] ?? 0) + row.market_value_krw;
  }
  const sectors = Object.entries(sectorMap).sort((a, b) => b[1] - a[1]).slice(0, 6);

  function Bar({ pct, color }: { pct: number; color: string }) {
    return (
      <div className="h-1.5 rounded-full bg-[var(--color-bg-tertiary)] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-3 flex flex-col gap-4">
      <div>
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">통화 비중</p>
        {currencies.map(([currency, val]) => {
          const pct = (val / total) * 100;
          return (
            <div key={currency} className="mb-1.5">
              <div className="flex justify-between text-[10px] font-mono mb-0.5">
                <span className="text-[var(--color-text-secondary)]">{currency}</span>
                <span className="text-[var(--color-text-primary)]">{pct.toFixed(1)}%</span>
              </div>
              <Bar pct={pct} color="var(--color-primary)" />
            </div>
          );
        })}
      </div>
      <div>
        <p className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mb-2">섹터 비중</p>
        {sectors.map(([sector, val]) => {
          const pct = (val / total) * 100;
          return (
            <div key={sector} className="mb-1.5">
              <div className="flex justify-between text-[10px] font-mono mb-0.5">
                <span className="text-[var(--color-text-secondary)]">{sector}</span>
                <span className="text-[var(--color-text-primary)]">{pct.toFixed(1)}%</span>
              </div>
              <Bar pct={pct} color="var(--color-primary-dim)" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PortfolioPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-4 py-2 text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] border-b border-[var(--color-border)] shrink-0">
        PORTFOLIO
      </div>
      <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
        <Panel defaultSize={25} minSize={15} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            WATCHLIST
          </div>
          <div className="flex-1 overflow-auto p-2">
            <WatchlistWidget />
          </div>
        </Panel>

        <ResizeHandle />

        <Panel defaultSize={50} minSize={30} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            HOLDINGS
          </div>
          <div className="flex-1 overflow-auto">
            <PortfolioWidget />
          </div>
        </Panel>

        <ResizeHandle />

        <Panel defaultSize={25} minSize={15} className="flex flex-col overflow-hidden">
          <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-widest text-[var(--color-text-secondary)] border-b border-[var(--color-border)] shrink-0">
            BREAKDOWN
          </div>
          <BreakdownPanel />
        </Panel>
      </PanelGroup>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/panels/PortfolioPanel.tsx
git commit -m "feat(terminal/m4): add PortfolioPanel with 3-column Bloomberg layout"
```

---

## Task 9: IndexStrip 업데이트 (INDICES 레이블 + EST 시각)

**Files:**
- Modify: `frontend/components/terminal/IndexStrip.tsx`

좌측에 `INDICES ▾` 레이블, 우측에 `● Connected` + New York EST 시각 추가.

`useEffect`로 1초마다 시각 업데이트. `Intl.DateTimeFormat`으로 EST 시각 포맷.

- [ ] **Step 1: IndexStrip.tsx 수정**

기존 파일 전체를 아래로 교체:

```tsx
"use client";
import { useEffect, useState } from "react";
import { useQuotes } from "@/hooks/useQuotes";
import type { QuoteItem } from "@/lib/types";

function fmt(value: number, decimals: number): string {
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function QuoteCell({ label, item, decimals }: {
  label: string;
  item: QuoteItem | null | undefined;
  decimals: number;
}) {
  const up = item && item.change_pct > 0;
  const down = item && item.change_pct < 0;
  const changeColor = up
    ? "text-[var(--color-gain)]"
    : down
    ? "text-[var(--color-loss)]"
    : "text-[var(--color-text-secondary)]";
  const arrow = up ? "▲" : down ? "▼" : "";

  return (
    <div className="flex items-center gap-1.5 text-[11px] shrink-0">
      <span className="text-[var(--color-text-secondary)] font-mono">{label}</span>
      <span className="text-[var(--color-text-primary)] font-mono">
        {item ? fmt(item.price, decimals) : "—"}
      </span>
      {item && (
        <span className={`font-mono text-[10px] ${changeColor}`}>
          {arrow}{item.change_abs >= 0 ? "+" : ""}{fmt(item.change_abs, decimals)}{" "}
          ({item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%)
        </span>
      )}
    </div>
  );
}

const EST_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function IndexStrip() {
  const quotes = useQuotes();
  const [clock, setClock] = useState(() => EST_FORMATTER.format(new Date()));

  useEffect(() => {
    const id = setInterval(() => setClock(EST_FORMATTER.format(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      {/* 좌: INDICES 레이블 */}
      <span className="text-[9px] font-mono uppercase tracking-widest text-[var(--color-primary)] mr-4 shrink-0">
        INDICES ▾
      </span>

      {/* 시세 셀 */}
      <div className="flex items-center gap-6 flex-1 overflow-x-auto">
        <QuoteCell label="SPY"     item={quotes?.SPY}    decimals={2} />
        <QuoteCell label="QQQ"     item={quotes?.QQQ}    decimals={2} />
        <QuoteCell label="USD/KRW" item={quotes?.USDKRW} decimals={1} />
        <QuoteCell label="BTC"     item={quotes?.BTC}    decimals={0} />
      </div>

      {/* 우: Connected + EST 시각 */}
      <div className="flex items-center gap-2 shrink-0 ml-4">
        <span className="text-[9px] font-mono text-[var(--color-connected)]">● Connected</span>
        <span className="text-[10px] font-mono text-[var(--color-text-muted)]">NY {clock} EST</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: 오류 없음

- [ ] **Step 3: Commit**

```bash
git add frontend/components/terminal/IndexStrip.tsx
git commit -m "feat(terminal/m4): update IndexStrip with INDICES label and EST clock"
```

---

## Task 10: page.tsx 교체 + Shell.tsx 삭제

**Files:**
- Modify: `frontend/app/terminal/page.tsx`
- Delete: `frontend/components/terminal/Shell.tsx`

- [ ] **Step 1: page.tsx를 TabShell + terminal-dark 클래스로 교체**

```tsx
"use client";
import dynamic from "next/dynamic";
import { GlobalNav } from "@/components/terminal/GlobalNav";
import { IndexStrip } from "@/components/terminal/IndexStrip";
import { CommandPalette } from "@/components/terminal/CommandPalette";

const TabShell = dynamic(
  () => import("@/components/terminal/TabShell").then(m => m.TabShell),
  { ssr: false, loading: () => (
    <div className="flex-1 flex items-center justify-center text-xs font-mono text-[var(--color-text-secondary)]">
      터미널 로딩 중…
    </div>
  )}
);

export default function TerminalPage() {
  return (
    <div className="terminal-dark fixed inset-0 z-50 flex flex-col bg-[var(--color-bg-primary)] overflow-hidden">
      <GlobalNav />
      <IndexStrip />
      <TabShell />
      <CommandPalette />
    </div>
  );
}
```

- [ ] **Step 2: Shell.tsx 삭제**

```bash
rm frontend/components/terminal/Shell.tsx
```

- [ ] **Step 3: TypeScript 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: Shell.tsx 관련 import 에러 없음, 전체 오류 없음

- [ ] **Step 4: Commit**

```bash
git add frontend/app/terminal/page.tsx
git rm frontend/components/terminal/Shell.tsx
git commit -m "feat(terminal/m4): wire TabShell into page, remove old Shell"
```

---

## Task 11: 최종 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: TypeScript 전체 체크**

```bash
cd frontend && npx tsc --noEmit 2>&1
```
Expected: 0 errors

- [ ] **Step 2: 개발 서버 실행 (이미 실행 중이 아니면)**

```bash
cd frontend && npm run dev &
sleep 5
```

- [ ] **Step 3: gstack-browse 스크린샷 — MARKETS 탭**

`/terminal` (또는 `/terminal?tab=markets`) 접속 후 스크린샷. 확인 항목:
- Bloomberg 다크 배경 (`#0a0a0a`)
- GlobalNav에 5개 탭 + LLM \<GO\> 버튼
- IndexStrip에 `INDICES ▾` + `● Connected` + EST 시각
- Row 1: 8개 Market Overview 타일 (SPY/QQQ/BTC는 실데이터, 나머지는 `—` + API 필요)
- Row 2: WATCHLIST | CHART placeholder | TOP NEWS placeholder 3분할

- [ ] **Step 4: 탭 전환 확인**

PORTFOLIO, RESEARCH, TOOLS, AI 탭 클릭 → URL에 `?tab=` 반영, 패널 전환 확인

- [ ] **Step 5: 드래그 리사이즈 확인**

Row 2 패널 경계를 드래그해서 폭 조절이 되는지 확인

- [ ] **Step 6: 콘솔 에러 확인**

`duplicate key` 에러 또는 hydration 에러 없음 확인

- [ ] **Step 7: 최종 Commit (변경 사항이 있으면)**

```bash
git add -p  # 수정된 파일만 선택적으로 스테이징
git commit -m "fix(terminal/m4): post-QA fixes"
```

---

## 완료 기준 체크리스트

- [ ] `npx tsc --noEmit` 오류 없음
- [ ] `/terminal` Bloomberg 다크 테마 렌더링
- [ ] 5개 탭 클릭 시 `?tab=` query param 반영 + 패널 전환
- [ ] SPY/QQQ/BTC 실데이터, DJI/VIX/WTI/GOLD/US10Y `—` + "API 필요"
- [ ] Row 2 경계 드래그 폭 조절 가능
- [ ] Row 3 포트폴리오 총 평가액 실데이터
- [ ] `● Connected` + EST 시각 표시
- [ ] `duplicate key` 콘솔 에러 없음
