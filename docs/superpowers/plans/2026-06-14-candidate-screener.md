# Candidate Screener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or equivalent task-by-task execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a candidate screener that finds stocks outside the user's current watchlist from Russell 1000, NASDAQ100, S&P500, KOSPI, and KOSDAQ, ranks them with configurable filters, and lets the user add selected candidates to a watchlist.

**Architecture:** Add a Russell 1000 universe provider and candidate-specific DB tables. Reuse existing price, fundamentals, quant score, growth score, and timing infrastructure for broad, lightweight scoring. Avoid expensive ChoiceStock collection for the full universe and final-candidate states; collect ChoiceStock only after the user adds a ticker to a watchlist.

**Tech Stack:** Python/FastAPI/DuckDB/SQLAlchemy/Pandas/APScheduler backend; Next.js/TypeScript/SWR frontend; pytest, py_compile, ESLint for verification.

---

## Current Constraints

- Natural-language output must stay Korean.
- Manual file edits use `apply_patch`.
- Do not revert unrelated dirty files. `data/kospi200_tickers.json` and `data/kosdaq150_tickers.json` may be dirty from prior data refreshes.
- Read APIs should prefer DB/cache. External provider calls belong in scheduled jobs, manual refresh, or explicit hydrate flows.
- ChoiceStock public HTML must not be collected for the full Russell 1000 universe.
- ChoiceStock public HTML must not be collected for `watching` or final-candidate-only status.
- ChoiceStock public HTML may be collected only after the user adds the ticker to a watchlist.
- Candidate scores are screening/ranking aids, not buy recommendations.

## File Map

- Modify `core/data/universe_provider.py`
  - Add Russell 1000 provider.
  - Keep cached JSON default behavior.
  - Add provider to monthly refresh.
- Modify `core/repository.py`
  - Add `candidate_universe_members`, `candidate_scores`, `candidate_shortlist`.
  - Add repository helpers.
- Create `core/candidates/scorer.py`
  - Build deduped US/KR candidate pools.
  - Compute candidate score and component scores.
- Modify `core/scheduler.py`
  - Add candidate scoring jobs.
- Create `api/routers/candidates.py`
  - Candidate list, refresh, shortlist, add-watchlist endpoints.
- Modify `api/main.py`
  - Include candidates router.
- Modify `api/models.py`
  - Add candidate response/request models.
- Modify `frontend/lib/api.ts`, `frontend/lib/types.ts`
  - Candidate API client/types.
- Create `frontend/app/candidates/page.tsx`
  - Candidate screener UI.
- Modify `frontend/components/nav.tsx`
  - Add navigation item.
- Optional later:
  - Telegram daily candidate digest.

---

## Task 1: Russell 1000 Universe Provider

**Files:**
- Modify `core/data/universe_provider.py`
- Add `data/russell1000_tickers.json` when provider is run

- [ ] Add `get_russell1000_tickers(refresh: bool = False)`.
- [ ] Preferred source order:
  - iShares IWB holdings CSV if available.
  - FTSE/LSEG public source if accessible.
  - Stable public fallback only if needed.
- [ ] Normalize symbols to app convention:
  - Replace `.` with `-` for US tickers.
  - Uppercase.
  - Remove blank/cash rows.
- [ ] Add `russell1000` to `UNIVERSE_PROVIDERS`.
- [ ] Add label to `UNIVERSE_LABELS`.
- [ ] Ensure `get_tickers("russell1000")` reads cache by default.
- [ ] Ensure `refresh_all_tickers()` includes Russell 1000.
- [ ] Verify:

```bash
python - <<'PY'
from core.data.universe_provider import get_tickers
xs = get_tickers("russell1000")
print(len(xs), xs[:5])
PY
```

Expected: loads from cache if present; otherwise provider refresh must create cache.

---

## Task 2: Candidate DB Schema

**Files:**
- Modify `core/repository.py`
- Create `tests/test_candidate_repository.py`

- [ ] Add `candidate_universe_members`.
- [ ] Add `candidate_scores`.
- [ ] Add `candidate_shortlist`.
- [ ] Add helpers:
  - `upsert_candidate_universe_members(rows)`
  - `get_candidate_universe_members(universe, as_of=None)`
  - `upsert_candidate_scores(rows)`
  - `get_latest_candidate_scores(region=None, universe_group=None)`
  - `upsert_candidate_shortlist(user_id, ticker, universe_group, status, memo=None)`
  - `get_candidate_shortlist(user_id, as_of=None)`
- [ ] Candidate shortlist status semantics:
  - `new`: not explicitly stored unless needed; candidate has no user action.
  - `watching`: user marked as final candidate / under review.
  - `added`: user added the ticker to a watchlist.
  - `dismissed`: user excluded the candidate.
- [ ] Default candidate queries must exclude:
  - existing watchlist tickers,
  - `watching` candidates,
  - `added` candidates,
  - `dismissed` candidates.
- [ ] Excluded statuses must remain queryable through explicit filters/tabs.
- [ ] Repository tests cover upsert/read for all three tables.
- [ ] Verify:

```bash
pytest tests/test_candidate_repository.py -q
```

---

## Task 3: Candidate Scoring Service

**Files:**
- Create `core/candidates/scorer.py`
- Optional create `core/candidates/__init__.py`

- [ ] Create US pool:
  - `russell1000 ∪ sp500 ∪ nasdaq100`
  - dedupe by ticker.
- [ ] Create KR pool:
  - KOSPI and KOSDAQ broad lists or current KOSPI/KOSDAQ filtered providers.
  - v1 may start with `kospi200` and `kosdaq150` until full KOSPI/KOSDAQ source is stabilized.
- [ ] Reuse existing data where possible:
  - `quant_scores`
  - growth score columns
  - OHLCV cache
  - timing analyzer
  - fundamentals snapshots/extended provider
- [ ] Compute components:
  - `growth_score`
  - `quality_score`
  - `valuation_score`
  - `momentum_score`
  - `timing_score`
  - `liquidity_score`
- [ ] Compute `candidate_score`.
- [ ] Save raw inputs to `raw_json`.
- [ ] Produce default outputs:
  - US Top30
  - KOSPI Top10
  - KOSDAQ Top10
- [ ] Do not call ChoiceStock in this service.
- [ ] Add a small deterministic unit test for score calculation.

---

## Task 4: Scheduler Jobs

**Files:**
- Modify `core/scheduler.py`

- [ ] Add `candidate_score_us_job`.
- [ ] Add `candidate_score_kr_job`.
- [ ] Suggested schedules:
  - US: daily 07:30 KST.
  - KR: daily 16:30 KST.
- [ ] Add job registry entries.
- [ ] Add APScheduler registrations.
- [ ] Mark bootstrap enabled for manual initial run.
- [ ] Verify:

```bash
python - <<'PY'
from core.scheduler import get_job_definitions
for job in get_job_definitions():
    if job["id"].startswith("candidate"):
        print(job)
PY
```

---

## Task 5: Candidates API

**Files:**
- Create `api/routers/candidates.py`
- Modify `api/main.py`
- Modify `api/models.py`

- [ ] Add `CandidateScoreOut`.
- [ ] Add `CandidateFilterIn` or query params.
- [ ] Add `CandidateShortlistIn`.
- [ ] Endpoints:
  - `GET /api/candidates`
  - `POST /api/candidates/refresh`
  - `PUT /api/candidates/{ticker}/shortlist`
  - `POST /api/candidates/{ticker}/add-watchlist`
- [ ] Filtering should happen on stored candidate scores.
- [ ] Query options:
  - `region`
  - `universe_group`
  - `sector`
  - `preset`
  - `exclude_watchlist`
  - `exclude_watching`
  - `hide_dismissed`
  - `status`
  - `limit`
  - `min_market_cap`
  - `min_liquidity`
  - `max_rsi`
  - `require_above_ma200`
  - `max_forward_pe`
  - `max_peg`
  - `min_roe`
- [ ] Add tests for list/filter/add-watchlist.

---

## Task 6: Candidate UI

**Files:**
- Create `frontend/app/candidates/page.tsx`
- Modify `frontend/lib/api.ts`
- Modify `frontend/lib/types.ts`
- Modify `frontend/components/nav.tsx`

- [ ] Add nav item: `후보발굴`.
- [ ] Build first screen as the actual candidate table, not a landing page.
- [ ] Controls:
  - Region segmented control: 미국/국장.
  - Preset select: 균형형/성장 우선/밸류 우선/타이밍 우선/눌림 대기형.
  - Sector select.
  - Exclude watchlist toggle.
  - Exclude watching toggle.
  - Hide dismissed toggle.
  - Numeric filters for market cap/liquidity/Forward PER/PEG/ROE/RSI.
- [ ] Status tabs:
  - 신규 후보.
  - 검토 중.
  - 관심종목 편입.
  - 제외됨.
- [ ] Results:
  - US Top30.
  - KOSPI Top10.
  - KOSDAQ Top10.
  - Score breakdown.
  - Timing badge.
  - Add to watchlist button.
  - Dismiss button.
- [ ] Keep dense, scan-friendly dashboard style.
- [ ] Mobile uses the existing desktop-canvas approach unless the app-wide policy changes.
- [ ] Verify in browser at desktop and mobile viewport.

---

## Task 7: Candidate Detail And Watchlist Handoff

**Files:**
- Modify `frontend/app/candidates/page.tsx`
- Reuse existing stock/ticker detail components where possible.

- [ ] Clicking a row opens a detail panel.
- [ ] Detail shows:
  - Selected ticker sticky header.
  - Price/EMA chart.
  - Score breakdown.
  - Timing check.
  - Data status.
- [ ] Add to watchlist:
  - Calls watchlist API.
  - Marks candidate status as `added`.
  - Does not immediately run ChoiceStock for all candidates.
  - Does not run ChoiceStock for `watching` or final-candidate-only status.
  - After adding to a watchlist, normal watchlist/ChoiceStock daily cache path handles detailed data.

---

## Task 8: Telegram Digest v2

**Files:**
- Modify `core/scheduler.py`
- Possibly modify `core/telegram.py`

- [ ] Add optional `candidate_daily_digest`.
- [ ] Send only if enabled.
- [ ] Default message:

```text
[후보 발굴] YYYY-MM-DD

미국 Top 후보
1. TICKER score ...

국장 Top 후보
1. TICKER score ...
```

- [ ] Keep channel separate or use `daily` channel based on env.

---

## Suggested Build Order

1. Task 1 and Task 2.
2. Task 3 with a minimal US-only scorer.
3. Task 5 API.
4. Task 6 UI.
5. Add KR scoring.
6. Add detail/shortlist polish.
7. Add Telegram digest.

## Non-Goals For v1

- Do not collect ChoiceStock for all Russell 1000 symbols.
- Do not collect ChoiceStock for final candidates unless they are added to a watchlist.
- Do not attempt all US listed stocks.
- Do not provide buy/sell recommendation language.
- Do not add real-time candidate ranking.
- Do not replace existing `/growth` page yet.
