# Korean Growth Results Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KOSPI 200과 KOSDAQ 150 성장주 점수 응답이 `NaN` 때문에 실패하지 않고 화면에 표시되게 한다.

**Architecture:** 숫자 정규화는 공통 재귀 헬퍼로 분리한다. `quant_scores` 저장 직전과 growth API 응답 직전에 모두 적용해 신규 데이터와 기존 저장 데이터를 함께 보호한다. 프론트는 SWR 오류를 빈 목록으로 숨기지 않고 사용자에게 표시한다.

**Tech Stack:** Python, FastAPI, DuckDB, pytest, Next.js, SWR, TypeScript

---

### Task 1: 숫자 정규화 회귀 테스트

**Files:**
- Modify: `tests/test_growth_api.py`
- Create: `core/data/normalization.py`

- [ ] 국내 점수 행에 `float("nan")`을 저장하고 `/api/growth/scores`가 `200`과 `null`을 반환하는 실패 테스트를 추가한다.
- [ ] 테스트를 실행해 JSON 직렬화 오류로 실패하는지 확인한다.
- [ ] `normalize_finite_numbers()`를 구현한다.
- [ ] API 응답 경계에 헬퍼를 적용하고 테스트 통과를 확인한다.

### Task 2: 저장 경계 보호

**Files:**
- Modify: `core/repository.py`
- Modify: `tests/test_growth_repository.py`

- [ ] `upsert_quant_scores()`가 비유한 숫자를 `None`으로 저장하는 실패 테스트를 추가한다.
- [ ] 저장 직전 정규화를 적용한다.
- [ ] repository 및 growth API 테스트를 실행한다.

### Task 3: 화면 오류 노출

**Files:**
- Modify: `frontend/app/growth/page.tsx`

- [ ] scores와 top 요청 오류를 SWR에서 수신한다.
- [ ] API 오류가 있으면 빈 목록 대신 오류 안내를 표시한다.
- [ ] scoped ESLint와 `git diff --check`를 실행한다.

### Task 4: 실제 국내 응답 검증

- [ ] API 프로세스 reload 후 KOSPI 200과 KOSDAQ 150 요청이 `200`인지 서버 로그로 확인한다.
- [ ] 관련 pytest를 실행한다.
