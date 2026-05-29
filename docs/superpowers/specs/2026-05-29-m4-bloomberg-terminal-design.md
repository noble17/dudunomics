# M4 Bloomberg Terminal UI — Design Spec

**Date:** 2026-05-29  
**Status:** Approved  
**Scope:** `/terminal` 페이지 전면 재설계. 기존 `/portfolio`, `/holdings`, `/backtest`, `/screener` 페이지는 변경 없음.

---

## 1. 목표

Bloomberg Terminal 스타일의 고밀도 금융 터미널 UI로 `/terminal` 페이지를 재설계한다.  
다크 테마, 5개 탭 내비게이션, 실데이터/placeholder 명확 구분, 패널 드래그 리사이즈를 제공한다.

---

## 2. 아키텍처

### 2.1 페이지 구조

```
/terminal
├── GlobalNav          — 탭 + 명령창 + AI 버튼 + 유저 메뉴
├── IndexStrip         — 실시간 시세 (기존 M3 컴포넌트 유지, 다크 스타일 적용)
└── TabShell           — 활성 탭에 따라 패널 레이아웃 전환
    ├── MarketsPanel   — 기본 화면
    ├── PortfolioPanel — 기존 포트폴리오 데이터, 다크 스타일
    ├── ResearchPanel  — 기존 퀀트 스크리너, 다크 스타일
    ├── ToolsPanel     — 기존 백테스트, 다크 스타일
    └── AiPanel        — placeholder ("M6에서 연결")
```

### 2.2 탭 상태 관리

- 탭 상태는 URL query param `?tab=markets` (기본값 `markets`)
- 새로고침 시 탭 유지, 링크 공유 가능
- 유효하지 않은 tab 값은 `markets`로 fallback

### 2.3 기존 컴포넌트 재활용

| 컴포넌트 | 재활용 방식 |
|---|---|
| `IndexStrip` | 그대로 유지, CSS 변수로 다크 스타일 자동 적용 |
| `WatchlistWidget` | MarketsPanel 좌측에 배치 |
| `PortfolioWidget` | PortfolioPanel 중앙에 배치 |
| `ScreenerWidget` | ResearchPanel 전체에 배치 |
| `BacktestWidget` | ToolsPanel 전체에 배치 |

---

## 3. 테마 시스템

### 3.1 CSS 변수 (다크 테마 — Bloomberg 스타일)

기존 CSS 변수를 Bloomberg 다크 테마 값으로 **교체**한다.

```css
/* 배경 */
--color-bg-primary:       #0a0a0a;
--color-bg-secondary:     #0f0f0f;
--color-bg-tertiary:      #141414;

/* 테두리 */
--color-border:           #1a1a1a;
--color-border-subtle:    #111111;

/* 텍스트 */
--color-text-primary:     #ffffff;
--color-text-secondary:   #888888;
--color-text-muted:       #444444;

/* 포인트 컬러 (Bloomberg 오렌지) */
--color-primary:          #ff6600;
--color-primary-dim:      #cc5200;

/* 손익 (한국 컨벤션: 상승=빨강, 하락=파랑) */
--color-gain:             #ff4444;
--color-loss:             #4488ff;

/* 상태 */
--color-connected:        #44aa44;
--color-placeholder:      #333333;
```

### 3.2 타이포그래피

- 폰트: `'Courier New', monospace` (터미널 전체), UI 요소는 `system-ui`
- 기본 font-size: 11px (고밀도)
- 패널 헤더: 9px, uppercase, letter-spacing: 1px, `--color-primary`

---

## 4. 컴포넌트 설계

### 4.1 GlobalNav (교체)

```
[Dudunomics로고] [MARKETS] [PORTFOLIO] [RESEARCH] [TOOLS] [AI]   [LLM<GO> 명령창 ⌘K] [AI COPILOT] [유저메뉴]
```

- 활성 탭: `border-top: 2px solid var(--color-primary)`, background `--color-bg-tertiary`
- 비활성 탭: `color: --color-text-muted`, hover 시 `--color-text-secondary`
- 명령창: 기존 `CommandPalette` 트리거 유지, Bloomberg `LLM <GO>` 스타일 인풋처럼 표시
- `AI COPILOT` 버튼: placeholder (M6에서 기능 연결)

파일: `frontend/components/terminal/GlobalNav.tsx` 교체

### 4.2 IndexStrip (스타일만 업데이트)

- 기존 로직 유지 (M3 useQuotes 훅)
- 좌측에 `INDICES ▾` 레이블 추가
- 우측에 `● Connected` + 현재 시각 (New York EST) 추가
- 파일: `frontend/components/terminal/IndexStrip.tsx` 소폭 수정

### 4.3 TabShell

활성 탭에 따라 패널 컴포넌트를 렌더링하는 컨테이너.

```tsx
// URL: /terminal?tab=markets (기본값)
const TAB_MAP = {
  markets:   <MarketsPanel />,
  portfolio: <PortfolioPanel />,
  research:  <ResearchPanel />,
  tools:     <ToolsPanel />,
  ai:        <AiPanel />,
}
```

파일: `frontend/components/terminal/TabShell.tsx` 신규

### 4.4 MarketsPanel (신규 — 기본 화면)

3-row 레이아웃, `react-resizable-panels`로 수직 분할 조절 가능.

**Row 1 — Market Overview 타일 (height: 80px)**

8개 고정 타일: `SPY | QQQ | DJI | VIX | US10Y | WTI | GOLD | BTC/USD`

- 데이터 있는 것 (SPY, QQQ, BTC): 실제 값 표시 (기존 `/api/quotes` 사용)
- 데이터 없는 것 (DJI, VIX, WTI 등): `—` + `"API 필요"` 표시 (절대 가짜 숫자 금지)
- 각 타일: ticker, 가격, 등락률(▲/▼ + %), 색상은 KR 컨벤션

**Row 2 — 3분할 패널 (flex-1, 남은 높이 전부)**

`react-resizable-panels` 수평 3분할, 각 패널 경계 드래그 가능.

| 패널 | 내용 | 데이터 |
|---|---|---|
| 좌 (기본 20%) | Watchlist | 기존 WatchlistWidget |
| 중 (기본 50%) | Chart | placeholder ("캔들 차트 — M5에서 연결") |
| 우 (기본 30%) | Top News | placeholder ("뉴스 — M6에서 연결") |

**Row 3 — 포트폴리오 요약 + AI (height: 72px)**

| 패널 | 내용 |
|---|---|
| 좌 (50%) | MY PORTFOLIO: 총 평가액, 수익률, 오늘 손익 (기존 `/api/portfolio/snapshot` 사용) |
| 우 (50%) | AI ASSISTANT placeholder ("Gemini API — M6에서 연결") |

파일: `frontend/components/terminal/panels/MarketsPanel.tsx` 신규

### 4.5 PortfolioPanel (신규)

기존 `PortfolioWidget` + `WatchlistWidget`을 Bloomberg 스타일로 재배치.

```
[좌 (25%): Watchlist] | [중 (50%): 포트폴리오 테이블] | [우 (25%): 섹터/통화 비중]
```

- 섹터/통화 비중 패널: 기존 데이터 활용, 차트는 간단한 bar로

파일: `frontend/components/terminal/panels/PortfolioPanel.tsx` 신규

### 4.6 ResearchPanel (신규)

기존 `ScreenerWidget`을 full-width Bloomberg 스타일로 감싸는 래퍼.

파일: `frontend/components/terminal/panels/ResearchPanel.tsx` 신규

### 4.7 ToolsPanel (신규)

기존 `BacktestWidget`을 full-width Bloomberg 스타일로 감싸는 래퍼.

파일: `frontend/components/terminal/panels/ToolsPanel.tsx` 신규

### 4.8 AiPanel (신규)

```
[중앙 정렬]
AI ASSISTANT
Gemini API — M6에서 연결 예정
[버튼: API 키 설정] (비활성 placeholder)
```

파일: `frontend/components/terminal/panels/AiPanel.tsx` 신규

---

## 5. 파일 변경 목록

| 파일 | 변경 |
|---|---|
| `frontend/app/terminal/page.tsx` | TabShell 사용하도록 교체 |
| `frontend/components/terminal/GlobalNav.tsx` | Bloomberg 스타일로 전면 교체 |
| `frontend/components/terminal/IndexStrip.tsx` | 레이블/시각 추가 (소폭) |
| `frontend/components/terminal/Shell.tsx` | 제거 (TabShell로 대체) |
| `frontend/components/terminal/TabShell.tsx` | **신규** |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | **신규** |
| `frontend/components/terminal/panels/PortfolioPanel.tsx` | **신규** |
| `frontend/components/terminal/panels/ResearchPanel.tsx` | **신규** |
| `frontend/components/terminal/panels/ToolsPanel.tsx` | **신규** |
| `frontend/components/terminal/panels/AiPanel.tsx` | **신규** |
| `frontend/app/globals.css` (또는 테마 파일) | Bloomberg 다크 CSS 변수 적용 |
| `frontend/lib/stores/workspace.ts` | duplicate-key 버그 픽스 (이미 완료) |

기존 `WidgetFrame`, `WidgetRegistry`, `widgets/*` 파일은 PortfolioPanel 등에서 내부적으로 계속 사용하므로 유지.

---

## 6. 데이터 정책

플랜 품질 기준 준수:

| 상태 | 표시 방식 |
|---|---|
| 실시간 데이터 있음 | 실제 값 + `● live` |
| 지연 데이터 | 값 + `⚠ 지연` |
| API 키 필요 | `—` + `"API 필요"` 회색 텍스트 |
| M5/M6 미구현 | `placeholder` 박스 + `"M5에서 연결"` 텍스트 |

**절대 금지:** 가짜 숫자로 실제처럼 보이는 표시.

---

## 7. 기존 기능 호환성

- `/portfolio`, `/holdings`, `/backtest`, `/screener` 페이지 변경 없음
- 기존 `/terminal` URL 유지 (탭 기본값 `markets`)
- WorkspaceLayout 타입/API는 유지 (패널 비율 저장에 계속 사용)
- JWT 인증 흐름 변경 없음

---

## 8. 완료 기준

1. `npx tsc --noEmit` 오류 없음
2. `/terminal` 접속 시 Bloomberg 다크 테마 렌더링
3. 5개 탭 클릭 시 각 패널로 전환 (`?tab=` query param 반영)
4. Market Overview 타일 — SPY/QQQ/BTC 실제 값, 나머지 `—` + "API 필요"
5. Row 2 패널 경계 드래그로 폭 조절 가능
6. Portfolio 요약 (Row 3 좌측) 실제 수익률 표시
7. gstack-browse `/terminal` 스크린샷으로 시각 확인
8. `duplicate key` 콘솔 에러 없음
