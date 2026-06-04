# 스크리너 섹터/인더스트리 필터 + CFO 필터 제거

**날짜:** 2026-05-31  
**범위:** 프론트엔드 전용 (API 변경 없음)

## 목표

1. 스크리너 사이드바에 섹터/인더스트리 2단계 필터 추가
2. 의미 없는 CFO 음수 하드 필터 제거 (S&P 500 기준 503개 중 12개만 해당)

## 배경

밸류에이션 오버홀(M9 이후)로 백엔드 `/api/screener/scores` 응답에 `sector`, `industry` 필드가 추가됐으나 프론트엔드가 이를 활용하지 않고 있음. 데이터는 S&P 500 기준 11개 섹터, 111개 인더스트리로 구성.

## 설계

### 데이터 흐름

- 필터링은 전량 클라이언트 사이드 (기존 ma200/cfo 패턴 동일)
- API 호출 변경 없음
- 섹터/인더스트리 목록은 `scores` 배열에서 useMemo로 동적 추출

### 필터 적용 순서

```
scores
  → ma200 하드 필터 (체크 시)
  → sector 필터 (선택된 경우)
  → industry 필터 (선택된 경우)
  → 가중치 기반 정렬 → topN(50)
```

### UI 구조 (사이드바)

```
[유니버스]
  <select> SP500 / Nasdaq100 / ...

[팩터 가중치]
  슬라이더 × 5

[하드 필터]
  ☑ 200일 MA 하회 제외        ← cfo 체크박스 제거

[섹터 / 인더스트리]
  <select> 전체 섹터 / Technology / ...
  <select> 전체 인더스트리 / ... (섹터 미선택 시 disabled)

[결과 요약]
  N / 503개 종목
```

- 섹터 변경 시 인더스트리 자동 리셋 (`""`)
- 인더스트리는 선택된 섹터에 속한 것만 표시

## 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `lib/types.ts` | `QuantScore`에 `sector`, `industry` 추가; `hardFilters` 타입에서 `cfo` 제거 |
| `app/screener/page.tsx` | `sectorFilter`/`industryFilter` state; 목록 useMemo; filteredCount 수정; props 전달 |
| `components/screener/factor-sidebar.tsx` | CFO 체크박스 제거; 섹터/인더스트리 셀렉트 추가 |
| `components/screener/ranking-table.tsx` | CFO 필터 로직 제거; 섹터/인더스트리 필터 추가 |

## 완료 기준

- [ ] 섹터 선택 시 해당 섹터 종목만 테이블에 표시
- [ ] 인더스트리 선택 시 해당 인더스트리 종목만 표시
- [ ] 섹터 "전체" 선택 시 인더스트리 드롭다운 disabled
- [ ] 섹터 변경 시 인더스트리 자동 리셋
- [ ] CFO 체크박스 제거됨
- [ ] filteredCount가 현재 필터 조합을 정확히 반영
