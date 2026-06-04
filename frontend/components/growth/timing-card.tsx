import type { GrowthTiming, TimingReason } from "@/lib/types";

function Signal({ label, value }: { label: string; value?: boolean | null }) {
  const tone = value === true ? "border-rise/40 bg-rise/10 text-rise" : value === false ? "border-border text-muted-foreground" : "border-border text-muted-foreground";
  return <span className={`rounded border px-2 py-1 text-xs ${tone}`}>{label}</span>;
}

const STATUS_LABEL = {
  suitable: "적합",
  watch: "관망",
  unsuitable: "부적합",
  unknown: "데이터 부족",
};

const VOLUME_LEVEL_LABEL: Record<NonNullable<GrowthTiming["volume_level"]>, string> = {
  quiet: "부족",
  normal: "보통",
  increased: "증가",
  strong: "강함",
  explosive: "폭발",
};

const VOLUME_DIRECTION_LABEL: Record<NonNullable<GrowthTiming["volume_direction"]>, string> = {
  bullish: "양봉",
  bearish: "음봉",
  flat: "보합",
};

const RSI_LEVEL_LABEL: Record<NonNullable<GrowthTiming["rsi_level"]>, string> = {
  oversold: "과매도",
  neutral: "중립",
  overheated: "과열 주의",
  extreme_overheated: "극단 과열",
};

const PULLBACK_STAGE_LABEL: Record<NonNullable<GrowthTiming["pullback_stage"]>, string> = {
  approach: "눌림목 접근",
  lower: "눌림목 하단",
  breakdown: "이탈 주의",
  none: "아님",
};

function compact(value?: number | null) {
  return value == null ? "-" : value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function ratio(value?: number | null) {
  return value == null ? "-" : `${value.toFixed(2)}x`;
}

function rsiValue(value?: number | null, level = "-") {
  return value == null ? "-" : `${value.toFixed(2)} (${level})`;
}

function reasonList(title: string, reasons?: TimingReason[], tone = "text-muted-foreground") {
  if (!reasons?.length) return null;
  return (
    <div className="space-y-1">
      <p className={`text-[11px] font-medium ${tone}`}>{title}</p>
      {reasons.map((reason) => (
        <p key={reason.code} className="text-xs text-muted-foreground">{reason.message}</p>
      ))}
    </div>
  );
}

export function TimingCard({ data }: { data?: GrowthTiming }) {
  const status = data?.status ?? "unknown";
  const accent = status === "suitable" ? "text-rise" : status === "unsuitable" ? "text-fall" : "text-muted-foreground";
  const volumeLevel = data?.volume_level ? VOLUME_LEVEL_LABEL[data.volume_level] : "-";
  const volumeDirection = data?.volume_direction ? VOLUME_DIRECTION_LABEL[data.volume_direction] : "-";
  const rsiLevel = data?.rsi_level ? RSI_LEVEL_LABEL[data.rsi_level] : "-";
  const pullbackStage = data?.pullback_stage ? PULLBACK_STAGE_LABEL[data.pullback_stage] : "-";
  const watchReasons = data?.downgrade_reasons?.length
    ? data.downgrade_reasons
    : status === "watch"
      ? data?.warning_reasons ?? []
      : [];
  const showWarningList = !(status === "watch" && watchReasons.length);
  const sufficiency = data?.data_sufficiency;
  const missing = sufficiency
    ? [
        !sufficiency.ema20 ? "EMA20" : null,
        !sufficiency.ema50 ? "EMA50" : null,
        !sufficiency.ema200 ? "EMA200" : null,
        !sufficiency.rsi ? "RSI" : null,
        !sufficiency.volume ? "20일 평균 거래량" : null,
      ].filter(Boolean)
    : [];

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between">
        <p className="text-[11px] font-medium tracking-[0.18em] text-primary">TIMING CHECK</p>
        <span className={`font-heading text-lg ${accent}`}>{STATUS_LABEL[status]}</span>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Signal label="EMA 정배열" value={data?.aligned} />
        <Signal label="눌림목" value={data?.pullback} />
        <Signal label="거래량 폭발" value={data?.volume_explosion} />
      </div>
      {missing.length > 0 && (
        <div className="mt-4 rounded-lg border border-primary/25 bg-primary/5 p-3">
          <p className="text-xs font-medium text-primary">부분 타이밍 분석</p>
          <p className="mt-1 text-xs text-muted-foreground">
            계산 가능 지표는 표시했고, {missing.join(", ")}은 데이터가 더 필요합니다.
          </p>
        </div>
      )}
      {data?.reason && <p className="mt-4 text-xs text-muted-foreground">{data.reason}</p>}
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <p className="text-muted-foreground">현재가 <span className="float-right font-data text-foreground">{data?.close?.toFixed(2) ?? "-"}</span></p>
        <p className="text-muted-foreground">눌림목 <span className="float-right text-foreground">{pullbackStage}</span></p>
        <p className="text-muted-foreground">EMA20 <span className="float-right font-data text-foreground">{data?.ema20?.toFixed(2) ?? "-"}</span></p>
        <p className="text-muted-foreground">EMA50 <span className="float-right font-data text-foreground">{data?.ema50?.toFixed(2) ?? "-"}</span></p>
        <p className="text-muted-foreground">EMA200 <span className="float-right font-data text-foreground">{data?.ema200?.toFixed(2) ?? "-"}</span></p>
        <p className="text-muted-foreground">거래량 <span className="float-right font-data text-foreground">{compact(data?.volume)}</span></p>
        <p className="text-muted-foreground">20일 평균 <span className="float-right font-data text-foreground">{compact(data?.avg_volume20)}</span></p>
        <p className="text-muted-foreground">거래량 배율 <span className="float-right font-data text-foreground">{ratio(data?.volume_ratio)}</span></p>
        <p className="text-muted-foreground">거래량 단계 <span className="float-right text-foreground">{volumeDirection} · {volumeLevel}</span></p>
        <p className="text-muted-foreground">RSI 14 <span className="float-right font-data text-foreground">{rsiValue(data?.rsi14, rsiLevel)}</span></p>
      </div>
      {watchReasons.length ? (
        <div className="mt-4 rounded-lg border border-fall/30 bg-fall/5 p-3">
          <p className="text-xs font-medium text-fall">
            {data?.downgrade_reasons?.length ? "관망 전환 사유" : "관망 사유"}
          </p>
          <div className="mt-2 space-y-1">
            {watchReasons.map((reason) => (
              <p key={reason.code} className="text-xs text-muted-foreground">{reason.message}</p>
            ))}
          </div>
        </div>
      ) : null}
      <div className="mt-4 grid gap-3">
        {reasonList("긍정 신호", data?.positive_reasons, "text-rise")}
        {showWarningList ? reasonList("주의 신호", data?.warning_reasons, "text-fall") : null}
      </div>
    </section>
  );
}
