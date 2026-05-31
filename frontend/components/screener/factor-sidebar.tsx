"use client";

import type { FactorWeights } from "@/lib/types";

interface Props {
  universe: string;
  onUniverseChange: (u: string) => void;
  weights: FactorWeights;
  onWeightsChange: (w: FactorWeights) => void;
  hardFilters: { ma200: boolean };
  onHardFiltersChange: (f: { ma200: boolean }) => void;
  sectorFilter: string;
  onSectorChange: (s: string) => void;
  industryFilter: string;
  onIndustryChange: (i: string) => void;
  sectors: string[];
  industries: string[];
  totalCount: number;
  filteredCount: number;
}

const FACTOR_LABELS: { key: keyof FactorWeights; label: string }[] = [
  { key: "momentum",     label: "가격 모멘텀" },
  { key: "valuation",    label: "밸류에이션" },
  { key: "eps_momentum", label: "EPS 모멘텀" },
  { key: "quality",      label: "퀄리티" },
  { key: "technical",    label: "기술적 지표" },
];

function normalizeWeights(w: FactorWeights): FactorWeights {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (total === 0) return { momentum: 20, valuation: 20, eps_momentum: 20, quality: 20, technical: 20 };
  return Object.fromEntries(
    Object.entries(w).map(([k, v]) => [k, Math.round((v / total) * 100)])
  ) as unknown as FactorWeights;
}

export function FactorSidebar({
  universe, onUniverseChange,
  weights, onWeightsChange,
  hardFilters, onHardFiltersChange,
  sectorFilter, onSectorChange,
  industryFilter, onIndustryChange,
  sectors, industries,
  totalCount, filteredCount,
}: Props) {
  const norm = normalizeWeights(weights);
  const total = Object.values(norm).reduce((a, b) => a + b, 0);

  const handleSlider = (key: keyof FactorWeights, val: number) => {
    onWeightsChange({ ...weights, [key]: val });
  };

  return (
    <aside className="sticky top-20 w-56 shrink-0 flex flex-col gap-4">
      {/* 유니버스 선택 */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">유니버스</p>
        <select
          value={universe}
          onChange={(e) => onUniverseChange(e.target.value)}
          className="w-full rounded border border-border bg-muted px-2 py-1 text-sm"
        >
          <option value="sp500">S&amp;P 500</option>
          <option value="nasdaq100">Nasdaq 100</option>
          <option value="kospi200">KOSPI 200</option>
          <option value="kosdaq150">KOSDAQ 150</option>
        </select>
      </div>

      {/* 팩터 가중치 */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">팩터 가중치</p>
          <span className={`text-xs font-bold ${total === 100 ? "text-green-600" : "text-amber-500"}`}>
            합계 {total}%
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {FACTOR_LABELS.map(({ key, label }) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="text-foreground">{label}</span>
                <span className="font-bold text-blue-600">{norm[key]}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={weights[key]}
                onChange={(e) => handleSlider(key, Number(e.target.value))}
                className="w-full accent-blue-500"
              />
            </div>
          ))}
        </div>
      </div>

      {/* 하드 필터 */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">하드 필터</p>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={hardFilters.ma200}
            onChange={(e) => onHardFiltersChange({ ma200: e.target.checked })}
          />
          200일 MA 하회 제외
        </label>
      </div>

      {/* 섹터 / 인더스트리 */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">섹터 / 인더스트리</p>
        <select
          value={sectorFilter}
          onChange={(e) => onSectorChange(e.target.value)}
          className="w-full rounded border border-border bg-muted px-2 py-1 text-sm mb-2"
        >
          <option value="">전체 섹터</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={industryFilter}
          onChange={(e) => onIndustryChange(e.target.value)}
          disabled={!sectorFilter}
          className="w-full rounded border border-border bg-muted px-2 py-1 text-sm disabled:opacity-40"
        >
          <option value="">전체 인더스트리</option>
          {industries.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
      </div>

      {/* 결과 요약 */}
      <p className="text-xs text-muted-foreground">
        {filteredCount} / {totalCount}개 종목
      </p>
    </aside>
  );
}
