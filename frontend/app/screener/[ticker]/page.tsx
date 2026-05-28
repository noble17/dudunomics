// frontend/app/screener/[ticker]/page.tsx
"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { screenerApi } from "@/lib/api";
import { RadarChart } from "@/components/screener/radar-chart";
import { FactorBars } from "@/components/screener/factor-bars";
import { MetricGrid } from "@/components/screener/metric-grid";
import { NoteForm } from "@/components/screener/note-form";

export default function TickerDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: score, isLoading } = useSWR(
    ticker ? `/api/screener/ticker/${ticker}` : null,
    () => screenerApi.ticker(ticker)
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) router.push(`/screener/${search.trim().toUpperCase()}`);
  };

  const radarPoints = score
    ? [
        { label: "모멘텀",   value: score.pct_momentum     ?? 0 },
        { label: "밸류",     value: score.pct_valuation    ?? 0 },
        { label: "EPS",      value: score.pct_eps_momentum ?? 0 },
        { label: "퀄리티",   value: score.pct_quality      ?? 0 },
        { label: "기술적",   value: score.pct_technical    ?? 0 },
      ]
    : [];

  const factorBars = score
    ? [
        { label: "가격 모멘텀", sublabel: "12-1M",       value: score.pct_momentum     },
        { label: "밸류에이션",  sublabel: "FWD PER+PBR", value: score.pct_valuation    },
        { label: "EPS 모멘텀",  sublabel: "1M+3M 추세",  value: score.pct_eps_momentum },
        { label: "퀄리티",      sublabel: "ROE+D/E",     value: score.pct_quality      },
        { label: "기술적 지표", sublabel: "RSI+200MA",   value: score.pct_technical    },
      ]
    : [];

  const validPcts = score
    ? [score.pct_momentum, score.pct_valuation, score.pct_eps_momentum, score.pct_quality, score.pct_technical].filter((v): v is number => v !== null)
    : [];
  const composite = validPcts.length > 0 ? validPcts.reduce((a, b) => a + b, 0) / validPcts.length : null;

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <form onSubmit={handleSearch} className="flex items-center gap-3 bg-muted/30 rounded-lg px-4 py-3 border border-border">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="티커 검색 (예: AAPL)"
          className="rounded border border-border bg-background px-2 py-1.5 text-sm w-40"
        />
        <button type="submit" className="rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground">이동</button>
        {score && (
          <>
            <span className="text-xl font-black text-foreground ml-2">{score.ticker}</span>
            <span className="text-sm text-muted-foreground">{score.company_name}</span>
            <div className="ml-auto bg-blue-100 text-blue-800 rounded-md px-3 py-1 text-sm font-bold">
              종합 {composite?.toFixed(2) ?? "—"}
              {composite !== null && (
                <span className="text-xs text-muted-foreground ml-1">
                  / 상위 {Math.round((1 - composite) * 100)}%
                </span>
              )}
            </div>
          </>
        )}
        {isLoading && <span className="text-sm text-muted-foreground">로딩 중...</span>}
      </form>

      {score && (
        <div className="flex gap-4 items-start">
          {/* 좌측: 레이더 + 팩터바 + 재무지표 */}
          <div className="flex-1 min-w-0 flex flex-col gap-4">
            {/* 레이더 + 팩터바 */}
            <div className="flex gap-4">
              <div className="w-44 h-44 shrink-0">
                <RadarChart points={radarPoints} />
              </div>
              <div className="flex-1 rounded-lg border border-border bg-background p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
                  팩터별 백분위 (vs S&amp;P 500)
                </p>
                <FactorBars bars={factorBars} />
              </div>
            </div>

            {/* 재무 지표 3×3 그리드 */}
            <div className="rounded-lg border border-border bg-background p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">재무 지표</p>
              <MetricGrid score={score} />
            </div>
          </div>

          {/* 우측: 투자 의견 기록 */}
          <div className="w-52 shrink-0 rounded-lg border border-border bg-background p-4 h-full">
            <NoteForm ticker={score.ticker} />
          </div>
        </div>
      )}
    </div>
  );
}
