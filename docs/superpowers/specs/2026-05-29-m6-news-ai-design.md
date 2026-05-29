# M6 — 뉴스 패널 + AI 어시스턴트 설계

**날짜:** 2026-05-29  
**브랜치:** feat/nextjs-fastapi-migration  
**목표:** MarketsPanel의 두 placeholder를 실제 기능으로 교체
- Row 2 우측: TOP NEWS (FMP 뉴스 피드)
- Row 3 우측: AI ASSISTANT (Gemini 요약 + 채팅 오버레이)

---

## 1. 범위

### 포함
- `GET /api/news?ticker=&limit=` — FMP proxy, 5분 메모리 캐시
- `GET /api/ai/summary?ticker=` — Gemini Flash 한국어 3문장 요약, 10분 캐시
- `POST /api/ai/chat` — Gemini SSE 스트리밍 채팅 (context: ticker + 현재가 + 뉴스 3개)
- `NewsPanel` 컴포넌트 (뉴스 카드 리스트)
- `AIStatusBar` 컴포넌트 (72px 바, 요약 텍스트 + 클릭 핸들러)
- `AIOverlay` 컴포넌트 (전체 화면 슬라이드업 채팅 패널)
- pytest 4개 이상

### 제외
- 뉴스 DB 저장 (캐시는 메모리에만)
- 멀티턴 히스토리 서버사이드 영속화
- Gemini 모델 선택 UI

---

## 2. 백엔드

### 2.1 `api/routers/news.py`

```
GET /api/news?ticker=AMZN&limit=10
```

- FMP endpoint: `https://financialmodelingprep.com/api/v3/stock_news?tickers={ticker}&limit={limit}&apikey={FMP_API_KEY}`
- 캐시: `_cache: dict[str, tuple[list, float]]` — `(data, expires_at)` 패턴, TTL 300초
- FMP 키 없으면(env 미설정 또는 placeholder): `503 {"detail": "FMP_API_KEY not configured"}`
- FMP 응답 매핑: `title, publishedDate, url, site, image` → `NewsItem` Pydantic 모델
- 인증: JWT (`current_user` Depends)

```python
class NewsItem(BaseModel):
    title: str
    published_date: str
    url: str
    site: str
    image: str | None = None

class NewsOut(BaseModel):
    ticker: str
    items: list[NewsItem]
```

### 2.2 `api/routers/ai.py`

#### `GET /api/ai/summary?ticker=AMZN`

- 내부적으로 `GET /api/news?ticker=AMZN&limit=3` 데이터 + 현재가(quotesApi or yfinance 단건) 취득
- Gemini Flash (`gemini-1.5-flash`) 호출:
  ```
  System: 당신은 주식 분석 어시스턴트입니다. 간결하고 객관적인 한국어로 답하세요.
  User: {ticker} 현재가 {price}. 최근 뉴스: {news_titles}. 3문장 이내로 시장 동향을 요약해주세요.
  ```
- 캐시: `_summary_cache: dict[str, tuple[str, float]]`, TTL 600초
- 인증: JWT

#### `POST /api/ai/chat` (SSE 스트리밍)

Request body:
```python
class ChatRequest(BaseModel):
    messages: list[dict]          # [{role: "user"|"assistant", content: str}]
    ticker: str | None = None
```

- ticker 제공 시 system prompt에 컨텍스트 주입:
  ```
  당신은 주식 분석 어시스턴트입니다. 현재 {ticker} ({price}원)에 대해 논의 중입니다.
  최근 뉴스: {top3_news_titles}
  ```
- Gemini streaming → `text/event-stream` 청크 응답
- `data: {text}\n\n` 포맷
- 인증: JWT

### 2.3 환경변수 추가

```
GEMINI_API_KEY=<user 제공>
# FMP_API_KEY는 기존 .env에 이미 있음
```

### 2.4 `api/main.py`

```python
from api.routers import news, ai
app.include_router(news.router)
app.include_router(ai.router)
```

---

## 3. 프론트엔드

### 3.1 `frontend/lib/types.ts` 추가

```typescript
export interface NewsItem {
  title: string;
  published_date: string;
  url: string;
  site: string;
  image: string | null;
}
export interface NewsOut {
  ticker: string;
  items: NewsItem[];
}
```

### 3.2 `frontend/lib/api.ts` 추가

```typescript
export const newsApi = {
  get: (ticker: string, limit = 10): Promise<NewsOut> =>
    fetcher(`/api/news?ticker=${ticker}&limit=${limit}`),
};

export const aiApi = {
  summary: (ticker: string): Promise<{ summary: string }> =>
    fetcher(`/api/ai/summary?ticker=${ticker}`),

  streamChat: async (
    messages: { role: string; content: string }[],
    ticker: string | null,
    onChunk: (text: string) => void,
  ): Promise<void> => {
    const res = await fetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, ticker }),
    });
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) onChunk(line.slice(6));
      }
    }
  },
};
```

### 3.3 `NewsPanel.tsx`

Props: `{ ticker: string }`

- SWR: `newsApi.get(ticker)`, `refreshInterval: 300_000` (5분)
- 로딩 중: 스켈레톤 3줄
- 에러/503: "뉴스 API 키 미설정" 메시지
- 뉴스 카드:
  ```
  [사이트명] 제목 (최대 2줄 ellipsis)
  MM/DD HH:mm
  ```
- 카드 클릭 → `window.open(url, "_blank")`
- 스타일: Bloomberg 다크 테마, `var(--color-*)` 토큰 사용

### 3.4 `AIStatusBar.tsx`

Props: `{ ticker: string; onOpen: () => void }`

- 기본 상태: "AI ASSISTANT" 라벨 + "클릭하여 분석 시작" 힌트 텍스트
- `onOpen` 호출 시 요약 fetch 시작 (클릭 트리거)
- 요약 로딩 중: 점멸 커서 텍스트
- 요약 표시: 한 줄 truncate, 오른쪽 "↑ 채팅 열기" 버튼
- 72px 고정 높이 유지

### 3.5 `AIOverlay.tsx`

Props: `{ ticker: string; summary: string | null; onClose: () => void }`

- `fixed inset-0 z-50` overlay, 반투명 배경 + 하단 슬라이드업 패널 (높이 60vh)
- 상단: "AI ASSISTANT — {ticker}" 헤더 + X 버튼
- 중간: 메시지 리스트 (user/assistant bubble)
  - 첫 메시지: summary 자동 표시 (assistant bubble)
- 하단: 입력창 + 전송 버튼
- 전송 시: `aiApi.streamChat(messages, ticker, onChunk)` 호출
- 스트리밍 청크: 마지막 assistant 버블에 텍스트 append
- Esc 키 → `onClose()`
- 스타일: `bg-[#111]` Bloomberg 다크

### 3.6 `MarketsPanel.tsx` 수정

```typescript
import { NewsPanel } from "../widgets/NewsPanel";
import { AIStatusBar } from "../widgets/AIStatusBar";
import { AIOverlay } from "../widgets/AIOverlay";

// 상태 추가
const [aiOpen, setAiOpen] = useState(false);
const [aiSummary, setAiSummary] = useState<string | null>(null);

// Row 2 Right Panel
<Panel defaultSize={30} minSize={12} className="...">
  <div className="px-3 py-1.5 ... shrink-0">TOP NEWS</div>
  <div className="flex-1 overflow-auto">
    <NewsPanel ticker={chartTicker} />
  </div>
</Panel>

// Row 3 Right
<div className="flex-1 flex flex-col justify-center px-4">
  <AIStatusBar
    ticker={chartTicker}
    onOpen={async () => {
      setAiOpen(true);
      const { summary } = await aiApi.summary(chartTicker);
      setAiSummary(summary);
    }}
  />
</div>

// overlay
{aiOpen && (
  <AIOverlay
    ticker={chartTicker}
    summary={aiSummary}
    onClose={() => { setAiOpen(false); setAiSummary(null); }}
  />
)}
```

---

## 4. 테스트

| 테스트 | 케이스 |
|--------|--------|
| `test_news_api.py` | 정상 응답(mock FMP) → 200 + items |
| `test_news_api.py` | FMP 키 미설정 → 503 |
| `test_news_api.py` | 인증 없이 → 401 |
| `test_ai_api.py` | summary 정상(mock Gemini) → 200 + summary 문자열 |
| `test_ai_api.py` | chat SSE → 스트리밍 청크 응답 확인 |
| `test_ai_api.py` | 인증 없이 → 401 |

---

## 5. 신규/수정 파일 목록

| 파일 | 변경 |
|------|------|
| `api/routers/news.py` | 신규 |
| `api/routers/ai.py` | 신규 |
| `api/models.py` | NewsItem, NewsOut 추가 |
| `api/main.py` | news, ai 라우터 등록 |
| `frontend/lib/types.ts` | NewsItem, NewsOut 추가 |
| `frontend/lib/api.ts` | newsApi, aiApi 추가 |
| `frontend/components/terminal/widgets/NewsPanel.tsx` | 신규 |
| `frontend/components/terminal/widgets/AIStatusBar.tsx` | 신규 |
| `frontend/components/terminal/widgets/AIOverlay.tsx` | 신규 |
| `frontend/components/terminal/panels/MarketsPanel.tsx` | NewsPanel + AIStatusBar + AIOverlay 연결 |
| `.env` / `.env.example` | GEMINI_API_KEY 추가 |
| `tests/test_news_api.py` | 신규 |
| `tests/test_ai_api.py` | 신규 |

---

## 6. 완료 기준

- `GET /api/news?ticker=SPY` → FMP 뉴스 리스트 반환
- `GET /api/ai/summary?ticker=SPY` → 한국어 3문장 요약
- `POST /api/ai/chat` → SSE 스트리밍 응답
- NewsPanel: 종목 전환 시 뉴스 갱신
- AIStatusBar: 클릭 → 요약 로딩 → 텍스트 표시
- AIOverlay: 슬라이드업 + 채팅 동작 + Esc 닫기
- pytest 6개 PASSED
- TypeScript 0 errors
