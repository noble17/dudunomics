const LABEL = "text-[11px] font-medium text-muted-foreground";

export interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  colored?: boolean;
  positive?: boolean;
}

export function KpiCard({ label, value, sub, colored, positive }: KpiCardProps) {
  const valueColor = colored
    ? positive ? "text-gain" : "text-loss"
    : "text-foreground";
  const accentBorder = colored
    ? positive ? "border-t-[3px] border-t-rise" : "border-t-[3px] border-t-fall"
    : "border-t-[3px] border-t-transparent";
  return (
    <div className={`border border-border bg-card p-4 min-w-0 ${accentBorder}`}>
      <p className={`${LABEL} mb-2 truncate`}>{label}</p>
      <p className={`font-data text-sm font-normal leading-tight whitespace-nowrap overflow-hidden ${valueColor}`}>{value}</p>
      {sub && (
        <p className={`mt-1 font-mono text-xs ${colored ? (positive ? "text-gain" : "text-loss") : "text-muted-foreground"}`}>
          {sub}
        </p>
      )}
    </div>
  );
}
