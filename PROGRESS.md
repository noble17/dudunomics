# Dudunomics 작업 진행 상황

## Part 0 — HTML 목업 프리뷰
- [x] 0-1. mockups/ 디렉토리 + ori.css + 4개 HTML 파일 생성
- [x] 0-2. 정적 SVG 차트 + holdings 편집기 3가지 상태 시연
- [x] 0-3. python3 -m http.server 4444 띄우기
- [x] 0-4. 사용자에게 http://localhost:4444 안내 및 시각 확인 요청
- [x] 0-5. 피드백 반영 및 최종 OK 수신 (→ Part A 착수 조건)

## Part A — Ori 디자인 시스템
- [x] A1. globals.css 전면 재작성 (Ori 토큰, semantic alias, radius 0 강제)
- [x] A2. layout.tsx 폰트 교체 (Inter/Poppins/Space Mono)
- [x] A3-1. nav.tsx — Chivo Mono + 오렌지 active border
- [x] A3-2. kpi-cards.tsx — Ori 토큰
- [x] A3-3. equity-curve.tsx — 오렌지 라인 + dark Tooltip
- [x] A3-4. holdings-table.tsx — Ori 토큰, gain/loss 색
- [x] A3-5. weight-pie.tsx — 오렌지 monochrome 8단계
- [x] A3-6. holdings-editor.tsx — Ori 토큰 (UI는 B7에서)
- [x] A3-7. backtest-result.tsx — Ori 토큰, 차트 다크
- [x] A3-8. ui/{button,input,card,badge}.tsx — Ori 토큰
- [x] A3-9. 페이지 헤딩 (portfolio/holdings/backtest) — font-heading 적용
- [x] A4. 시각 확인: 모든 페이지 검정 배경 + 0 radius + 오렌지 액센트

## Part B — KIS 자동조회/검색
- [x] B1. core/ids.py — to_kis_overseas(market) + market_from_ticker
- [x] B2-1. core/prices/kis.py — _get_api에 @lru_cache 적용
- [x] B2-2. core/prices/kis.py — lookup() 메서드 (fallback 순차 시도)
- [x] B2-3. core/prices/kis.py — search() 메서드
- [x] B3. core/repository.py — sector 컬럼 추가 + 마이그레이션 (market은 B1 이후)
- [x] B4. api/models.py — HoldingIn.sector, PortfolioRow.sector 추가
- [x] B4-2. api/models.py — TickerLookupOut, TickerSearchHit, HoldingIn.market (KIS 이후)
- [x] B5-1. api/routers/holdings.py — GET /lookup/{ticker}
- [x] B5-2. api/routers/holdings.py — GET /search
- [x] B6. frontend/lib/{types,api}.ts — sector 타입 추가
- [x] B7-0. holdings-editor.tsx — sector 입력 컬럼 추가
- [x] B7-1. holdings-editor.tsx — 검색 콤보박스 (debounce)
- [x] B7-2. holdings-editor.tsx — 🔍 조회 버튼 + fallback 드롭다운
- [x] B7-3. holdings-editor.tsx — 저장 시 market 포함
- [x] B8. portfolio.py — market 전파해서 snapshot 정확도 향상

## Dashboard 개선 (추가)
- [x] 도넛 차트 중앙 총액 레이블
- [x] 도넛 차트 범례 목록 (이름 + % + 만원)
- [x] 섹터 탭 추가 (전체/국장/미장/섹터)
- [x] 국내/해외 종목 테이블 섹터 배지
- [x] 국내/해외 종목 테이블 항상 표시 (빈 상태 메시지)

## Part C — Port 변경
- [x] C1. frontend/package.json — dev script -p 3333
- [x] C2. api CORS — localhost:3333 추가 (기본값 변경 + .env.example)
- [x] C3. README dev URL 갱신 (localhost:3000 → 3333)

## Part D — Upbit 디자인 시스템 마이그레이션

### D0. mockups 재작성 (구현 차단 게이트)
- [x] D0-1. 기존 mockups/ 삭제 (Ori 다크 테마)
- [x] D0-2. mockups/tokens.css 작성 (DESIGN.md §3 토큰)
- [x] D0-3. mockups/index.html — 토큰/컴포넌트 카탈로그
- [x] D0-4. mockups/portfolio.html — KPI + 도넛 + 보유 테이블
- [x] D0-5. mockups/holdings.html — 편집기 + 검색 드롭다운
- [x] D0-6. mockups/backtest.html — 폼 + 에쿼티 차트 + KPI
- [x] D0-7. 사용자 시각 확인 OK → frontend 착수

### D1. globals.css 재작성
- [x] D1-1. ClickUp 토큰 13종 제거
- [x] D1-2. :root shadcn 시맨틱 Upbit으로 치환
- [x] D1-3. --gain/--loss 의미 반전 + --error 신규 추가
- [x] D1-4. --chart-1~5 Upbit 톤 5색 팔레트
- [x] D1-5. --radius 9px → 4px
- [x] D1-6. 미사용 토큰(sidebar/gradient/surface) 정리
- [x] D1-7. .text-error 유틸리티 추가

### D2. 폰트 교체
- [x] D2-1. layout.tsx — Plus Jakarta 제거, Roboto + Noto Sans KR 로드
- [x] D2-2. globals.css — --font-sans/--font-heading/--font-mono 동기화

### D3. 컴포넌트 잔재 제거
- [x] D3-1. equity-curve.tsx hex 7곳 → 토큰
- [x] D3-2. return-bar.tsx hex 7곳 → 토큰 (L62 gain/loss 분기 포함)
- [x] D3-3. weight-pie.tsx COLORS 배열 → Upbit 톤
- [x] D3-4. backtest-result.tsx hex 6곳 → 토큰
- [x] D3-5. dashboard.tsx — bg-[#111111], hover Ori 잔재 제거
- [x] D3-6. holdings-table.tsx — 동일
- [x] D3-7. holdings-editor.tsx — thead/tbody/드롭다운/삭제 hover 4곳

### D4. 에러 토큰 분리
- [x] D4-1. portfolio/page.tsx L24 text-loss → text-error
- [x] D4-2. holdings-editor.tsx L356 삭제 버튼 text-loss → text-error
- [x] D4-3. holdings-editor.tsx L373 status 오류 분기 text-loss → text-error

### D5. 검증
- [x] D5-1. npm run build 통과 (typecheck + prod build)
- [x] D5-2. rg 헥스 잔재 0건 (#ff4f2b, #7b68ee, #202023, #292d34 없음)
- [x] D5-3. /portfolio 시각: 라이트 배경 확인 (상승/하락은 데이터 필요)
- [x] D5-4. /holdings 시각: 흰 카드 + 4px radius 버튼
- [x] D5-5. /backtest 시각: 라이트 배경 + Tooltip 코드 확인 (차트는 실행 시 검증)
- [x] D5-6. portfolio 에러 상태: 에러 메시지가 빨강 (#DD3C44)

## M1 — 멀티유저 JWT 인증 (커밋 a5c353a, 2026-05-28)

### M1.17 pytest (auth 라우터)
- [x] test_me_unauthenticated — 쿠키 없음 → 401
- [x] test_signup_success — 201 + Set-Cookie
- [x] test_signup_duplicate_email — 409
- [x] test_signup_short_password — 422
- [x] test_login_success — 200 + Set-Cookie
- [x] test_login_wrong_password — 401
- [x] test_me_after_login — 200 + 이메일 반환
- [x] test_user_data_isolation — user2 holdings → []

### M1.18~19 브라우저 검증
- [x] /login — 이메일/비밀번호 폼, 회원가입 링크 렌더링 확인
- [x] /signup — 이메일/비밀번호(6자 이상) 폼, 로그인 링크 렌더링 확인
- [x] LEGACY 계정(noble8543@gmail.com) 로그인 → /portfolio 리다이렉트 + 기존 종목 표시

### M1.20 부가 수정
- [x] core/repository.py: LEGACY 사용자 삽입 후 users_id_seq 진행 (nextval 호출)
- [x] tests/conftest 패턴 확장: LEGACY_USER_EMAIL/PASSWORD monkeypatch 삭제

---

## 검증
- [x] frontend build & typecheck 통과
- [x] curl /api/holdings/lookup/005930.KS → 삼성전자 정상
- [x] curl /api/holdings/lookup/JPM (market 없이) → NYSE fallback 성공
- [x] curl /api/holdings/lookup/INVALID → 422 + need_market
- [x] curl /api/holdings/search?q=삼성 → 후보 리스트 (yfinance → Yahoo autocomplete v6 교체)
- [x] UI: 새 행 추가 → "삼성" 검색 → 후보 선택 → 자동 채움 (005930.KS + 삼성전자(주) 채움)
- [x] UI: AAPL 입력 → 🔍 → Apple/USD/NASDAQ 채움
- [x] localhost:3333 접속 확인
