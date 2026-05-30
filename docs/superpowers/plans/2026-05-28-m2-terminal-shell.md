# M2 Terminal Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bloomberg 스타일 `/terminal` 페이지 — 3분할 패널(좌/중/우) + 드래그·리사이즈 위젯 그리드 + 워크스페이스 DB 영속화 + Cmd+K 명령창

**Architecture:** `react-resizable-panels`로 좌·중·우 3분할, 중앙에 `react-grid-layout`으로 드래그·리사이즈 위젯 그리드. Zustand로 클라이언트 상태 관리, FastAPI `/api/workspace` 엔드포인트로 레이아웃 JSON을 DuckDB에 사용자별 저장. `cmdk`로 Cmd+K 명령창 구현.

**Tech Stack:** react-resizable-panels, react-grid-layout, zustand, cmdk, FastAPI, DuckDB, Next.js 16 (Turbopack), SWR

---

## 파일 구조

```
# 신규 생성
api/routers/workspace.py
tests/test_workspace_api.py
frontend/app/terminal/layout.tsx
frontend/app/terminal/page.tsx
frontend/components/terminal/Shell.tsx
frontend/components/terminal/GlobalNav.tsx
frontend/components/terminal/IndexStrip.tsx
frontend/components/terminal/CommandPalette.tsx
frontend/components/terminal/WidgetFrame.tsx
frontend/components/terminal/WidgetRegistry.ts
frontend/components/terminal/widgets/Portfolio.tsx
frontend/components/terminal/widgets/Watchlist.tsx
frontend/components/terminal/widgets/Screener.tsx
frontend/components/terminal/widgets/Backtest.tsx
frontend/lib/stores/workspace.ts
frontend/lib/stores/command.ts

# 수정
core/repository.py               — user_workspaces DDL + get_workspace/save_workspace
api/main.py                      — workspace 라우터 등록
frontend/middleware.ts → frontend/proxy.ts  — Next.js 16 파일명 변경
frontend/lib/types.ts            — WorkspaceLayout 타입 추가
frontend/lib/api.ts              — workspaceApi 추가
frontend/components/nav.tsx      — /terminal 링크 추가
```

---

### Task 1: npm 의존성 설치

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 패키지 설치**

```bash
cd frontend
npm install react-grid-layout react-resizable-panels zustand cmdk
npm install --save-dev @types/react-grid-layout
```

- [ ] **Step 2: 설치 확인**

```bash
node -e "require('react-grid-layout'); require('react-resizable-panels'); require('zustand'); require('cmdk'); console.log('OK')"
```
Expected: `OK`

- [ ] **Step 3: 빌드 통과 확인**

```bash
npm run build 2>&1 | tail -5
```
Expected: 빌드 성공 (exit 0)

- [ ] **Step 4: 커밋**

```bash
cd ..
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(m2): install react-grid-layout, react-resizable-panels, zustand, cmdk"
```

---

### Task 2: middleware → proxy.ts 이름 변경

**Files:**
- Rename: `frontend/middleware.ts` → `frontend/proxy.ts`

- [ ] **Step 1: 파일 이름 변경**

```bash
mv frontend/middleware.ts frontend/proxy.ts
```

- [ ] **Step 2: 빌드 확인 (dev 서버 재시작 후 경고 없어야 함)**

```bash
cd frontend && npm run build 2>&1 | grep -i middleware || echo "경고 없음"
```
Expected: `경고 없음`

- [ ] **Step 3: /portfolio가 여전히 인증 필요 확인 (미들웨어 동작 검증)**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3333/portfolio
```
Expected: `307` (쿠키 없으면 /login으로 리다이렉트)

- [ ] **Step 4: 커밋**

```bash
cd ..
git add frontend/proxy.ts frontend/middleware.ts
git commit -m "fix: rename middleware.ts to proxy.ts for Next.js 16"
```

---

### Task 3: 백엔드 — user_workspaces DDL + Repository

**Files:**
- Modify: `core/repository.py`

- [ ] **Step 1: `_init_schema`에 user_workspaces 테이블 DDL 추가**

`core/repository.py`의 `_init_schema` 함수 안 `DDL` 문자열에 아래 테이블을 추가한다 (기존 `CREATE TABLE IF NOT EXISTS users (` 블록 이후 적절한 위치):

```python
    CREATE TABLE IF NOT EXISTS user_workspaces (
        user_id     INTEGER NOT NULL,
        name        TEXT NOT NULL DEFAULT 'default',
        layout_json TEXT NOT NULL DEFAULT '{}',
        updated_at  TIMESTAMP DEFAULT current_timestamp,
        PRIMARY KEY (user_id, name)
    );
```

- [ ] **Step 2: Repository 함수 2개 추가**

`core/repository.py` 끝에 추가:

```python
# ── Workspace ─────────────────────────────────────────────────────────────────

def get_workspace(user_id: int, name: str = "default") -> dict:
    with session() as s:
        row = s.execute(
            text("SELECT layout_json FROM user_workspaces WHERE user_id = :uid AND name = :n"),
            {"uid": user_id, "n": name},
        ).fetchone()
        import json
        return json.loads(row[0]) if row else {}


def save_workspace(user_id: int, layout: dict, name: str = "default") -> None:
    with session() as s:
        import json
        payload = json.dumps(layout, ensure_ascii=False)
        s.execute(text("""
            INSERT INTO user_workspaces (user_id, name, layout_json, updated_at)
            VALUES (:uid, :n, :payload, current_timestamp)
            ON CONFLICT (user_id, name) DO UPDATE SET
                layout_json = excluded.layout_json,
                updated_at  = excluded.updated_at
        """), {"uid": user_id, "n": name, "payload": payload})
        s.commit()
```

- [ ] **Step 3: 커밋**

```bash
git add core/repository.py
git commit -m "feat(m2): add user_workspaces table DDL and get/save_workspace repo functions"
```

---

### Task 4: 백엔드 — workspace 라우터

**Files:**
- Create: `api/routers/workspace.py`
- Modify: `api/main.py`

- [ ] **Step 1: workspace 라우터 생성**

```python
# api/routers/workspace.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth.deps import CurrentUser, current_user
import core.repository as repo

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceIn(BaseModel):
    layout: dict
    name: str = "default"


@router.get("")
def get_workspace(name: str = "default", user: CurrentUser = Depends(current_user)):
    return {"layout": repo.get_workspace(user.id, name), "name": name}


@router.put("")
def save_workspace(body: WorkspaceIn, user: CurrentUser = Depends(current_user)):
    repo.save_workspace(user.id, body.layout, body.name)
    return {"ok": True}
```

- [ ] **Step 2: api/main.py에 라우터 등록**

`api/main.py`의 import 블록에 추가:
```python
from api.routers.workspace import router as workspace_router
```

`app.include_router(screener_router)` 다음 줄에 추가:
```python
app.include_router(workspace_router)
```

- [ ] **Step 3: curl 동작 확인**

```bash
# 백엔드 재시작 후
curl -s http://localhost:8000/api/workspace | python3 -m json.tool
```
Expected: `401 Unauthorized` (인증 없이 접근 시)

- [ ] **Step 4: 커밋**

```bash
git add api/routers/workspace.py api/main.py
git commit -m "feat(m2): add GET/PUT /api/workspace endpoint"
```

---

### Task 5: 백엔드 — workspace pytest

**Files:**
- Create: `tests/test_workspace_api.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
# tests/test_workspace_api.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ws_client(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "ws@test.com", "password": "password123"})
    return c


def test_get_workspace_empty(ws_client):
    res = ws_client.get("/api/workspace")
    assert res.status_code == 200
    assert res.json() == {"layout": {}, "name": "default"}


def test_save_and_get_workspace(ws_client):
    layout = {
        "panels": [20, 55, 25],
        "center_widgets": [{"i": "w1", "type": "portfolio", "x": 0, "y": 0, "w": 6, "h": 8}],
    }
    res = ws_client.put("/api/workspace", json={"layout": layout})
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    res2 = ws_client.get("/api/workspace")
    assert res2.status_code == 200
    assert res2.json()["layout"] == layout


def test_workspace_isolation(fresh_db, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-32bytes-for-tests")
    monkeypatch.delenv("BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("LEGACY_USER_EMAIL", raising=False)
    monkeypatch.delenv("LEGACY_USER_PASSWORD", raising=False)
    from api.main import app
    c1 = TestClient(app)
    c1.post("/api/auth/signup", json={"email": "u1@test.com", "password": "password123"})
    c1.put("/api/workspace", json={"layout": {"widgets": ["portfolio"]}})

    c2 = TestClient(app)
    c2.post("/api/auth/signup", json={"email": "u2@test.com", "password": "password123"})
    res = c2.get("/api/workspace")
    assert res.json()["layout"] == {}
```

- [ ] **Step 2: 테스트 실행**

```bash
uv run pytest tests/test_workspace_api.py -v
```
Expected: 3 passed

- [ ] **Step 3: 커밋**

```bash
git add tests/test_workspace_api.py
git commit -m "test(m2): add workspace API pytest (empty/roundtrip/isolation)"
```

---

### Task 6: 프론트엔드 — 타입 + API 클라이언트

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: types.ts에 WorkspaceLayout 타입 추가**

`frontend/lib/types.ts` 끝에 추가:

```typescript
export interface WidgetItem {
  i: string;       // unique id (e.g. "w1")
  type: string;    // "portfolio" | "watchlist" | "screener" | "backtest"
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WorkspaceLayout {
  panels?: [number, number, number];  // [left%, center%, right%]
  center_widgets?: WidgetItem[];
  left_widget?: string | null;
  right_widget?: string | null;
}
```

- [ ] **Step 2: api.ts에 workspaceApi 추가**

`frontend/lib/api.ts`의 import에 `WorkspaceLayout` 추가:
```typescript
import type {
  ...,
  WorkspaceLayout,
} from "./types";
```

파일 끝에 추가:
```typescript
export const workspaceApi = {
  get: (name = "default") =>
    request<{ layout: WorkspaceLayout; name: string }>(`/api/workspace?name=${name}`),
  save: (layout: WorkspaceLayout, name = "default") =>
    request<{ ok: boolean }>("/api/workspace", {
      method: "PUT",
      body: JSON.stringify({ layout, name }),
    }),
};
```

- [ ] **Step 3: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error" | head -5
```
Expected: 출력 없음 (에러 없음)

- [ ] **Step 4: 커밋**

```bash
cd ..
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(m2): add WorkspaceLayout types and workspaceApi"
```

---

### Task 7: Zustand workspace store

**Files:**
- Create: `frontend/lib/stores/workspace.ts`

- [ ] **Step 1: stores 디렉토리 생성 + workspace store 작성**

```typescript
// frontend/lib/stores/workspace.ts
"use client";
import { create } from "zustand";
import type { WidgetItem, WorkspaceLayout } from "@/lib/types";
import { workspaceApi } from "@/lib/api";

let _saveTimer: ReturnType<typeof setTimeout> | null = null;

interface WorkspaceState {
  layout: WorkspaceLayout;
  loaded: boolean;
  loadWorkspace: () => Promise<void>;
  addWidget: (type: string) => void;
  removeWidget: (id: string) => void;
  updateGrid: (items: WidgetItem[]) => void;
  setPanels: (panels: [number, number, number]) => void;
  _scheduleSave: () => void;
}

let _widgetCounter = 0;
function nextId() {
  return `w${++_widgetCounter}`;
}

const DEFAULT_LAYOUT: WorkspaceLayout = {
  panels: [22, 53, 25],
  center_widgets: [
    { i: "w1", type: "portfolio", x: 0, y: 0, w: 12, h: 8 },
    { i: "w2", type: "watchlist", x: 0, y: 8, w: 6, h: 6 },
    { i: "w3", type: "screener", x: 6, y: 8, w: 6, h: 6 },
  ],
  left_widget: "watchlist",
  right_widget: null,
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  layout: DEFAULT_LAYOUT,
  loaded: false,

  loadWorkspace: async () => {
    try {
      const res = await workspaceApi.get();
      const incoming = res.layout;
      set({
        layout: Object.keys(incoming).length > 0 ? incoming : DEFAULT_LAYOUT,
        loaded: true,
      });
    } catch {
      set({ loaded: true });
    }
  },

  addWidget: (type: string) => {
    const { layout, _scheduleSave } = get();
    const existing = layout.center_widgets ?? [];
    const maxY = existing.reduce((m, w) => Math.max(m, w.y + w.h), 0);
    const item: WidgetItem = { i: nextId(), type, x: 0, y: maxY, w: 6, h: 6 };
    set({ layout: { ...layout, center_widgets: [...existing, item] } });
    _scheduleSave();
  },

  removeWidget: (id: string) => {
    const { layout, _scheduleSave } = get();
    set({
      layout: {
        ...layout,
        center_widgets: (layout.center_widgets ?? []).filter(w => w.i !== id),
      },
    });
    _scheduleSave();
  },

  updateGrid: (items: WidgetItem[]) => {
    const { layout, _scheduleSave } = get();
    set({ layout: { ...layout, center_widgets: items } });
    _scheduleSave();
  },

  setPanels: (panels) => {
    const { layout, _scheduleSave } = get();
    set({ layout: { ...layout, panels } });
    _scheduleSave();
  },

  _scheduleSave: () => {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => {
      workspaceApi.save(get().layout).catch(() => {});
    }, 800);
  },
}));
```

- [ ] **Step 2: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "^.+error" | head -5
```
Expected: 출력 없음

- [ ] **Step 3: 커밋**

```bash
cd ..
git add frontend/lib/stores/workspace.ts
git commit -m "feat(m2): add Zustand workspace store with debounced API save"
```

---

### Task 8: Zustand command store

**Files:**
- Create: `frontend/lib/stores/command.ts`

- [ ] **Step 1: command store 작성**

```typescript
// frontend/lib/stores/command.ts
"use client";
import { create } from "zustand";

interface CommandState {
  open: boolean;
  focusedTicker: string | null;
  openPalette: () => void;
  closePalette: () => void;
  setFocusedTicker: (ticker: string | null) => void;
}

export const useCommandStore = create<CommandState>((set) => ({
  open: false,
  focusedTicker: null,
  openPalette: () => set({ open: true }),
  closePalette: () => set({ open: false }),
  setFocusedTicker: (ticker) => set({ focusedTicker: ticker }),
}));
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/lib/stores/command.ts
git commit -m "feat(m2): add Zustand command store (palette open state + focused ticker)"
```

---

### Task 9: WidgetFrame + WidgetRegistry

**Files:**
- Create: `frontend/components/terminal/WidgetFrame.tsx`
- Create: `frontend/components/terminal/WidgetRegistry.ts`

- [ ] **Step 1: WidgetFrame 작성**

```tsx
// frontend/components/terminal/WidgetFrame.tsx
"use client";
import { X } from "lucide-react";

interface Props {
  title: string;
  onClose?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function WidgetFrame({ title, onClose, children, className = "" }: Props) {
  return (
    <div className={`flex flex-col h-full bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-sm overflow-hidden ${className}`}>
      <div
        className="widget-drag-handle flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] cursor-move select-none shrink-0"
        style={{ fontSize: "11px" }}
      >
        <span className="text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">
          {title}
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] p-0.5 rounded"
            onMouseDown={e => e.stopPropagation()}
          >
            <X size={12} />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-2">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: WidgetRegistry 작성**

```typescript
// frontend/components/terminal/WidgetRegistry.ts
import type { ComponentType } from "react";

export interface WidgetMeta {
  label: string;
  component: ComponentType<{ widgetId?: string }>;
  defaultW: number;
  defaultH: number;
}

// 실제 컴포넌트는 Task 10에서 추가됨
export const WIDGET_REGISTRY: Record<string, WidgetMeta> = {};

export function registerWidget(type: string, meta: WidgetMeta) {
  WIDGET_REGISTRY[type] = meta;
}
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/components/terminal/WidgetFrame.tsx frontend/components/terminal/WidgetRegistry.ts
git commit -m "feat(m2): add WidgetFrame and WidgetRegistry"
```

---

### Task 10: 위젯 4개 (thin wrappers)

**Files:**
- Create: `frontend/components/terminal/widgets/Portfolio.tsx`
- Create: `frontend/components/terminal/widgets/Watchlist.tsx`
- Create: `frontend/components/terminal/widgets/Screener.tsx`
- Create: `frontend/components/terminal/widgets/Backtest.tsx`

- [ ] **Step 1: Portfolio 위젯 작성**

```tsx
// frontend/components/terminal/widgets/Portfolio.tsx
"use client";
import useSWR from "swr";
import { portfolioApi } from "@/lib/api";
import { PortfolioDashboard } from "@/components/portfolio/dashboard";

export function PortfolioWidget() {
  const { data: snapshot, isLoading } = useSWR("/api/portfolio/current", portfolioApi.current, { refreshInterval: 30_000 });
  const { data: history } = useSWR("/api/portfolio/history?limit=8640", () => portfolioApi.history(), { refreshInterval: 60_000 });

  if (isLoading) return <div className="text-xs text-muted-foreground p-2">로딩 중…</div>;
  if (!snapshot) return null;
  return <PortfolioDashboard snapshot={snapshot} history={history ?? []} />;
}
```

- [ ] **Step 2: Watchlist 위젯 작성**

```tsx
// frontend/components/terminal/widgets/Watchlist.tsx
"use client";
import useSWR from "swr";
import { holdingsApi } from "@/lib/api";
import { useCommandStore } from "@/lib/stores/command";

export function WatchlistWidget() {
  const { data: holdings, isLoading } = useSWR("/api/holdings", holdingsApi.list, { refreshInterval: 30_000 });
  const setFocused = useCommandStore(s => s.setFocusedTicker);

  if (isLoading) return <div className="text-xs text-muted-foreground">로딩 중…</div>;
  if (!holdings?.length) return <div className="text-xs text-muted-foreground">보유종목 없음</div>;

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[var(--color-text-secondary)] border-b border-[var(--color-border)]">
          <th className="text-left py-1 pr-2">티커</th>
          <th className="text-right py-1 pr-2">수량</th>
          <th className="text-right py-1">수익률</th>
        </tr>
      </thead>
      <tbody>
        {holdings.map(h => (
          <tr
            key={h.ticker}
            className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-bg-primary)] cursor-pointer"
            onClick={() => setFocused(h.ticker)}
          >
            <td className="py-1 pr-2 font-mono font-medium text-[var(--color-text-primary)]">{h.ticker}</td>
            <td className="py-1 pr-2 text-right text-[var(--color-text-secondary)]">{h.quantity}</td>
            <td className="py-1 text-right text-[var(--color-text-secondary)]">—</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 3: Screener 위젯 작성**

```tsx
// frontend/components/terminal/widgets/Screener.tsx
"use client";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";

export function ScreenerWidget() {
  const { data: scores, isLoading } = useSWR("/api/screener/scores?universe=sp500", () => screenerApi.scores(), { refreshInterval: 300_000 });

  if (isLoading) return <div className="text-xs text-muted-foreground">로딩 중…</div>;
  if (!scores?.length) return <div className="text-xs text-muted-foreground">데이터 없음</div>;

  const top = scores.sort((a, b) => {
    const sa = (a.pct_momentum ?? 0) + (a.pct_quality ?? 0);
    const sb = (b.pct_momentum ?? 0) + (b.pct_quality ?? 0);
    return sb - sa;
  }).slice(0, 20);

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[var(--color-text-secondary)] border-b border-[var(--color-border)]">
          <th className="text-left py-1 pr-2">티커</th>
          <th className="text-right py-1 pr-2">모멘텀</th>
          <th className="text-right py-1">밸류</th>
        </tr>
      </thead>
      <tbody>
        {top.map(s => (
          <tr key={s.ticker} className="border-b border-[var(--color-border)]/50">
            <td className="py-1 pr-2 font-mono font-medium text-[var(--color-text-primary)]">{s.ticker}</td>
            <td className="py-1 pr-2 text-right">{s.pct_momentum != null ? `${(s.pct_momentum * 100).toFixed(0)}%` : "—"}</td>
            <td className="py-1 text-right">{s.pct_valuation != null ? `${(s.pct_valuation * 100).toFixed(0)}%` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Backtest 위젯 작성**

```tsx
// frontend/components/terminal/widgets/Backtest.tsx
"use client";
import Link from "next/link";

export function BacktestWidget() {
  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="text-[var(--color-text-secondary)]">백테스트 결과를 보려면 전체 페이지를 이용하세요.</p>
      <Link href="/backtest" className="text-[var(--color-primary)] hover:underline" target="_blank">
        백테스트 페이지 열기 →
      </Link>
    </div>
  );
}
```

- [ ] **Step 5: WidgetRegistry에 위젯 등록**

`frontend/components/terminal/WidgetRegistry.ts` 전체 내용을 아래로 교체:

```typescript
// frontend/components/terminal/WidgetRegistry.ts
import type { ComponentType } from "react";
import { PortfolioWidget } from "./widgets/Portfolio";
import { WatchlistWidget } from "./widgets/Watchlist";
import { ScreenerWidget } from "./widgets/Screener";
import { BacktestWidget } from "./widgets/Backtest";

export interface WidgetMeta {
  label: string;
  component: ComponentType;
  defaultW: number;
  defaultH: number;
}

export const WIDGET_REGISTRY: Record<string, WidgetMeta> = {
  portfolio: { label: "포트폴리오", component: PortfolioWidget, defaultW: 12, defaultH: 10 },
  watchlist: { label: "워치리스트", component: WatchlistWidget, defaultW: 6, defaultH: 8 },
  screener:  { label: "종목분석",   component: ScreenerWidget,  defaultW: 6, defaultH: 8 },
  backtest:  { label: "백테스트",   component: BacktestWidget,  defaultW: 6, defaultH: 6 },
};
```

- [ ] **Step 6: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "^.+error" | head -10
```
Expected: 에러 없음

- [ ] **Step 7: 커밋**

```bash
cd ..
git add frontend/components/terminal/widgets/ frontend/components/terminal/WidgetRegistry.ts
git commit -m "feat(m2): add 4 terminal widgets (Portfolio/Watchlist/Screener/Backtest) + registry"
```

---

### Task 11: IndexStrip

**Files:**
- Create: `frontend/components/terminal/IndexStrip.tsx`

- [ ] **Step 1: IndexStrip 작성 (M3 전까지 정적 placeholder)**

```tsx
// frontend/components/terminal/IndexStrip.tsx
"use client";

const INDICES = [
  { label: "SPY", value: "—", change: null },
  { label: "QQQ", value: "—", change: null },
  { label: "USD/KRW", value: "—", change: null },
  { label: "BTC", value: "—", change: null },
];

export function IndexStrip() {
  return (
    <div className="flex items-center gap-6 px-4 h-8 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0 overflow-x-auto">
      {INDICES.map(idx => (
        <div key={idx.label} className="flex items-center gap-1.5 text-xs shrink-0">
          <span className="text-[var(--color-text-secondary)] font-medium">{idx.label}</span>
          <span className="text-[var(--color-text-primary)] font-mono">
            {idx.value}
          </span>
          <span className="text-[var(--color-text-secondary)] text-[10px]">M3에서 실시간 연결</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/components/terminal/IndexStrip.tsx
git commit -m "feat(m2): add IndexStrip placeholder (M3에서 실시간 데이터 연결)"
```

---

### Task 12: CommandPalette (cmdk + Cmd+K)

**Files:**
- Create: `frontend/components/terminal/CommandPalette.tsx`

- [ ] **Step 1: CommandPalette 작성**

```tsx
// frontend/components/terminal/CommandPalette.tsx
"use client";
import { useEffect } from "react";
import { Command } from "cmdk";
import { useCommandStore } from "@/lib/stores/command";
import { useWorkspaceStore } from "@/lib/stores/workspace";
import { WIDGET_REGISTRY } from "./WidgetRegistry";

export function CommandPalette() {
  const { open, closePalette } = useCommandStore();
  const addWidget = useWorkspaceStore(s => s.addWidget);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        useCommandStore.getState().openPalette();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[20vh] bg-black/40"
      onClick={closePalette}
    >
      <div
        className="w-full max-w-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-sm shadow-xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <Command className="[&_[cmdk-input]]:w-full [&_[cmdk-input]]:px-4 [&_[cmdk-input]]:py-3 [&_[cmdk-input]]:text-sm [&_[cmdk-input]]:bg-transparent [&_[cmdk-input]]:outline-none [&_[cmdk-input]]:border-b [&_[cmdk-input]]:border-[var(--color-border)] [&_[cmdk-input]]:text-[var(--color-text-primary)]">
          <Command.Input placeholder="위젯 추가, 페이지 이동…" />
          <Command.List className="max-h-64 overflow-auto p-2">
            <Command.Empty className="text-xs text-[var(--color-text-secondary)] px-3 py-4">
              결과 없음
            </Command.Empty>
            <Command.Group heading={<span className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider px-2">위젯 추가</span>}>
              {Object.entries(WIDGET_REGISTRY).map(([type, meta]) => (
                <Command.Item
                  key={type}
                  value={`위젯 ${meta.label} ${type}`}
                  onSelect={() => { addWidget(type); closePalette(); }}
                  className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer text-[var(--color-text-primary)] data-[selected=true]:bg-[var(--color-bg-primary)]"
                >
                  <span>{meta.label} 추가</span>
                  <span className="ml-auto text-[10px] text-[var(--color-text-secondary)] font-mono">{type}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "^.+error" | head -5
```
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
cd ..
git add frontend/components/terminal/CommandPalette.tsx
git commit -m "feat(m2): add CommandPalette with Cmd+K shortcut and widget add commands"
```

---

### Task 13: GlobalNav

**Files:**
- Create: `frontend/components/terminal/GlobalNav.tsx`

- [ ] **Step 1: GlobalNav 작성 (terminal 전용 네비게이션)**

```tsx
// frontend/components/terminal/GlobalNav.tsx
"use client";
import Link from "next/link";
import { useCommandStore } from "@/lib/stores/command";
import { UserMenu } from "@/components/user-menu";
import useSWR from "swr";
import { request } from "@/lib/api-internal";

function useMe() {
  return useSWR("/api/auth/me", () =>
    fetch("/api/auth/me", { credentials: "include" }).then(r => r.ok ? r.json() : null)
  );
}

export function GlobalNav() {
  const openPalette = useCommandStore(s => s.openPalette);
  const { data: me } = useMe();

  return (
    <div className="flex items-center justify-between px-4 h-10 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      <div className="flex items-center gap-4">
        <Link href="/portfolio" className="font-heading text-sm font-bold text-[var(--color-text-primary)]">
          Dudunomics
        </Link>
        <span className="text-[var(--color-border)]">|</span>
        <span className="text-xs text-[var(--color-text-secondary)]">Terminal</span>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={openPalette}
          className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded px-2 py-1 hover:border-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <span>명령창</span>
          <kbd className="font-mono text-[10px] bg-[var(--color-bg-primary)] px-1 rounded">⌘K</kbd>
        </button>
        {me?.email && <UserMenu email={me.email} />}
      </div>
    </div>
  );
}
```

주의: `useMe`에서 직접 `fetch`를 사용함 (api.ts의 `request`는 401 시 redirect하므로).

- [ ] **Step 2: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "^.+error" | head -5
```
Expected: 에러 없음

- [ ] **Step 3: 커밋**

```bash
cd ..
git add frontend/components/terminal/GlobalNav.tsx
git commit -m "feat(m2): add terminal GlobalNav with Cmd+K button and user menu"
```

---

### Task 14: Shell (react-resizable-panels + react-grid-layout)

**Files:**
- Create: `frontend/components/terminal/Shell.tsx`

- [ ] **Step 1: CSS 임포트 파일 생성**

react-grid-layout이 요구하는 CSS를 전역 CSS에 추가한다.
`frontend/app/globals.css` 파일에 아래 두 줄을 맨 위에 추가:

```css
@import 'react-grid-layout/css/styles.css';
@import 'react-resizable/css/styles.css';
```

- [ ] **Step 2: Shell.tsx 작성**

```tsx
// frontend/components/terminal/Shell.tsx
"use client";
import { useEffect, useRef } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import ReactGridLayout, { type Layout } from "react-grid-layout";
import { useWorkspaceStore } from "@/lib/stores/workspace";
import { WidgetFrame } from "./WidgetFrame";
import { WIDGET_REGISTRY } from "./WidgetRegistry";
import { WatchlistWidget } from "./widgets/Watchlist";
import type { WidgetItem } from "@/lib/types";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 hover:bg-[var(--color-primary)] bg-[var(--color-border)] transition-colors mx-0.5" />
  );
}

function CenterGrid() {
  const { layout, updateGrid, removeWidget } = useWorkspaceStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const widgets = layout.center_widgets ?? [];

  const rglLayout: Layout[] = widgets.map(w => ({
    i: w.i, x: w.x, y: w.y, w: w.w, h: w.h,
  }));

  function onLayoutChange(newLayout: Layout[]) {
    const updated: WidgetItem[] = widgets.map(w => {
      const l = newLayout.find(n => n.i === w.i);
      return l ? { ...w, x: l.x, y: l.y, w: l.w, h: l.h } : w;
    });
    updateGrid(updated);
  }

  const containerWidth = containerRef.current?.clientWidth ?? 800;
  const rowHeight = 40;

  return (
    <div ref={containerRef} className="h-full overflow-auto">
      <ReactGridLayout
        layout={rglLayout}
        cols={12}
        rowHeight={rowHeight}
        width={containerWidth}
        draggableHandle=".widget-drag-handle"
        onLayoutChange={onLayoutChange}
        margin={[4, 4]}
        containerPadding={[4, 4]}
        resizeHandles={["se"]}
      >
        {widgets.map(w => {
          const meta = WIDGET_REGISTRY[w.type];
          if (!meta) return null;
          const Comp = meta.component;
          return (
            <div key={w.i}>
              <WidgetFrame
                title={meta.label}
                onClose={() => removeWidget(w.i)}
                className="h-full"
              >
                <Comp />
              </WidgetFrame>
            </div>
          );
        })}
      </ReactGridLayout>
    </div>
  );
}

export function Shell() {
  const { loadWorkspace, loaded, layout } = useWorkspaceStore();

  useEffect(() => {
    if (!loaded) loadWorkspace();
  }, [loaded, loadWorkspace]);

  const panels = layout.panels ?? [22, 53, 25];

  return (
    <PanelGroup direction="horizontal" className="flex-1 overflow-hidden">
      <Panel defaultSize={panels[0]} minSize={12} className="flex flex-col">
        <div className="px-2 py-1 text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider border-b border-[var(--color-border)]">
          워치리스트
        </div>
        <div className="flex-1 overflow-auto p-2">
          <WatchlistWidget />
        </div>
      </Panel>

      <ResizeHandle />

      <Panel defaultSize={panels[1]} minSize={30} className="flex flex-col overflow-hidden">
        <CenterGrid />
      </Panel>

      <ResizeHandle />

      <Panel defaultSize={panels[2]} minSize={12} className="flex flex-col">
        <div className="px-2 py-1 text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider border-b border-[var(--color-border)]">
          AI / 뉴스 (M4~M5)
        </div>
        <div className="flex-1 overflow-auto p-2 text-xs text-[var(--color-text-secondary)]">
          M4에서 뉴스+번역, M5에서 AI 어시스턴트 연결 예정
        </div>
      </Panel>
    </PanelGroup>
  );
}
```

- [ ] **Step 3: 빌드 확인**

```bash
cd frontend && npm run build 2>&1 | grep -E "^.+error" | head -10
```
Expected: 에러 없음

- [ ] **Step 4: 커밋**

```bash
cd ..
git add frontend/components/terminal/Shell.tsx frontend/app/globals.css
git commit -m "feat(m2): add Shell with react-resizable-panels + react-grid-layout center grid"
```

---

### Task 15: Terminal layout + page (조립)

**Files:**
- Create: `frontend/app/terminal/layout.tsx`
- Create: `frontend/app/terminal/page.tsx`
- Modify: `frontend/components/nav.tsx`

- [ ] **Step 1: terminal layout 작성 (full-screen, 루트 레이아웃 오버라이드)**

```tsx
// frontend/app/terminal/layout.tsx
export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
```

- [ ] **Step 2: terminal page 작성**

react-grid-layout은 SSR 불가이므로 Shell을 dynamic import로 감싼다.

```tsx
// frontend/app/terminal/page.tsx
"use client";
import dynamic from "next/dynamic";
import { GlobalNav } from "@/components/terminal/GlobalNav";
import { IndexStrip } from "@/components/terminal/IndexStrip";
import { CommandPalette } from "@/components/terminal/CommandPalette";

const Shell = dynamic(
  () => import("@/components/terminal/Shell").then(m => m.Shell),
  { ssr: false, loading: () => <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">터미널 로딩 중…</div> }
);

export default function TerminalPage() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--color-bg-primary)] overflow-hidden">
      <GlobalNav />
      <IndexStrip />
      <Shell />
      <CommandPalette />
    </div>
  );
}
```

- [ ] **Step 3: Nav에 터미널 링크 추가**

`frontend/components/nav.tsx`의 `links` 배열에 터미널 항목 추가:

```typescript
const links = [
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/holdings", label: "보유종목" },
  { href: "/backtest", label: "백테스트" },
  { href: "/screener", label: "종목분석" },
  { href: "/terminal", label: "터미널" },
];
```

- [ ] **Step 4: 빌드 확인 + 타입 에러 없음**

```bash
cd frontend && npm run build 2>&1 | tail -20
```
Expected: 빌드 성공, `/terminal` 라우트 포함

- [ ] **Step 5: 커밋**

```bash
cd ..
git add frontend/app/terminal/ frontend/components/nav.tsx
git commit -m "feat(m2): add /terminal page with full-screen shell, GlobalNav, IndexStrip, CommandPalette"
```

---

### Task 16: 브라우저 검증 (완료 정의 확인)

- [ ] **Step 1: 백엔드 재시작 확인**

```bash
curl -s http://localhost:8000/api/workspace -o /dev/null -w "%{http_code}"
```
Expected: `401`

- [ ] **Step 2: 프론트엔드 서버 확인**

```bash
curl -s http://localhost:3333/terminal -o /dev/null -w "%{http_code}"
```
Expected: `200`

- [ ] **Step 3: gstack-browse로 검증**

아래 체크리스트를 브라우저에서 확인:
1. http://localhost:3333/terminal 진입 → 로그인 페이지로 리다이렉트
2. 로그인 후 `/terminal` → GlobalNav + IndexStrip + 3분할 패널 렌더링
3. 중앙 그리드에 위젯 드래그 → 이동 확인
4. 위젯 우하단 핸들로 리사이즈 → 크기 변경 확인
5. 새로고침 → 동일 레이아웃 복원 (`/api/workspace`에서 로드)
6. Cmd+K → 명령창 열림 → "포트폴리오 추가" 선택 → 위젯 추가
7. × 버튼 → 위젯 제거

- [ ] **Step 4: PROGRESS.md 갱신**

`PROGRESS.md`에 M2 섹션 추가:
```markdown
## M2 — 터미널 셸 (commit [hash], 2026-05-28)
- [x] npm: react-grid-layout, react-resizable-panels, zustand, cmdk
- [x] 백엔드: user_workspaces DDL + GET/PUT /api/workspace
- [x] pytest: workspace (empty/roundtrip/isolation) 3개 통과
- [x] 프론트엔드: /terminal full-screen 페이지
- [x] Shell: react-resizable-panels 3분할 + react-grid-layout 중앙 그리드
- [x] 위젯 4개: Portfolio / Watchlist / Screener / Backtest
- [x] CommandPalette: Cmd+K + 위젯 추가 커맨드
- [x] IndexStrip: placeholder (M3에서 실시간 연결)
- [x] 워크스페이스 영속화: 새로고침 후 레이아웃 복원
```

- [ ] **Step 5: 최종 커밋**

```bash
git add PROGRESS.md
git commit -m "docs: M2 완료 체크 PROGRESS.md 갱신"
```

---

## Self-Review

**Spec coverage 확인:**

| 요구사항 | 구현 태스크 |
|---|---|
| `/terminal` 진입 → 3분할 패널 | Task 14, 15 |
| 드래그·리사이즈 위젯 | Task 14 (react-grid-layout) |
| 워크스페이스 영속화 | Task 3,4,5,7 |
| 다른 계정 = 다른 레이아웃 | Task 5 (isolation test) |
| Cmd+K 명령창 | Task 12 |
| 위젯: 워치리스트/포트폴리오 | Task 10 |
| npm 의존성 설치 | Task 1 |
| react-grid-layout SSR 대응 | Task 15 (dynamic import) |
| middleware → proxy 경고 수정 | Task 2 |

**Gap 확인:** 없음. 모든 M2 요구사항이 태스크에 매핑됨.

**주의사항:**
- Task 13 GlobalNav에서 `/api/auth/me`를 직접 fetch하므로 `api.ts`의 `request` 함수를 사용하지 않음 (401 redirect 방지)
- react-grid-layout은 클라이언트 전용 → `dynamic(..., {ssr: false})` 필수
- DuckDB `ON CONFLICT ... DO UPDATE` 문법은 DuckDB 1.x에서 지원됨 (기존 holdings upsert에서도 사용 중)
