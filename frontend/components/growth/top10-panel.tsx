"use client";

import type { GrowthScore } from "@/lib/types";

interface Props {
  scores: GrowthScore[];
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}

function signalLabel(score: GrowthScore) {
  if (score.timing_status === "suitable") return ["매수 적합", "border-rise/40 bg-rise/10 text-rise"];
  if (score.timing_downgrade_reasons?.length) return ["관망 사유 있음", "border-fall/40 bg-fall/10 text-fall"];
  if (score.timing_pullback_stage === "breakdown") return ["이탈 주의", "border-fall/40 bg-fall/10 text-fall"];
  if (score.timing_pullback_stage === "lower") return ["눌림목 하단", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_pullback_stage === "approach") return ["눌림목 접근", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_volume_direction === "bearish") return ["매도 압력", "border-fall/40 bg-fall/10 text-fall"];
  if (score.timing_volume_level === "explosive") return ["거래량 폭발", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_volume_level === "strong") return ["강한 거래량", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_volume_level === "increased") return ["거래량 증가", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_rsi_level === "extreme_overheated") return ["RSI 과열", "border-fall/40 bg-fall/10 text-fall"];
  if (score.timing_pullback) return ["눌림목 접근", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_volume_explosion) return ["거래량 확인", "border-primary/40 bg-primary/10 text-primary"];
  if (score.timing_aligned) return ["상승 추세", "border-border bg-muted text-muted-foreground"];
  if (score.timing_status === "unknown") return ["데이터 부족", "border-border bg-muted text-muted-foreground"];
  return ["추세 대기", "border-border bg-muted text-muted-foreground"];
}

export function Top10Panel({ scores, selectedTicker, onSelect }: Props) {
  if (scores.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border px-4 py-12 text-center">
        <p className="text-sm text-muted-foreground">현재 조건을 모두 통과한 종목이 없습니다.</p>
        <p className="mt-1 text-xs text-muted-foreground">시총 구간이나 섹터 필터를 바꿔보세요.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {scores.map((score, index) => {
        const [label, badgeClass] = signalLabel(score);
        return (
          <button
            key={score.ticker}
            type="button"
            onClick={() => onSelect(score.ticker)}
            className={`rounded-lg border px-3 py-3 text-left transition-colors hover:border-primary/60 hover:bg-primary/5 ${
              selectedTicker === score.ticker ? "border-primary bg-primary/10" : "border-border bg-card"
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="font-data text-[10px] text-muted-foreground">TOP {index + 1}</p>
                <p className="mt-1 font-data text-sm font-medium text-foreground">{score.ticker}</p>
              </div>
              <span className="font-data text-xl text-primary">{score.growth_composite?.toFixed(1) ?? "-"}</span>
            </div>
            <p className="mt-2 truncate text-xs text-muted-foreground">{score.company_name ?? score.sector ?? "-"}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
              <span>ROIC {score.raw_roic !== null ? `${(score.raw_roic * 100).toFixed(1)}%` : "-"}</span>
              <span>OPM {score.raw_oper_margin !== null ? `${(score.raw_oper_margin * 100).toFixed(1)}%` : "-"}</span>
              <span className={`rounded border px-1.5 py-0.5 ${badgeClass}`}>{label}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
