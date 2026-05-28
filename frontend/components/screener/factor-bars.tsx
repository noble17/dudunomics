// frontend/components/screener/factor-bars.tsx
interface FactorBar { label: string; sublabel: string; value: number | null }

export function FactorBars({ bars }: { bars: FactorBar[] }) {
  return (
    <div className="flex flex-col gap-2">
      {bars.map(({ label, sublabel, value }) => {
        const v = value ?? 0;
        const color = v >= 0.7 ? "bg-green-500" : v <= 0.3 ? "bg-red-400" : "bg-amber-400";
        const textColor = v >= 0.7 ? "text-green-600" : v <= 0.3 ? "text-red-500" : "text-amber-500";
        return (
          <div key={label}>
            <div className="flex justify-between text-xs mb-0.5">
              <span className="text-foreground">
                {label} <span className="text-muted-foreground">{sublabel}</span>
              </span>
              <span className={`font-bold ${textColor}`}>
                {value !== null ? value.toFixed(2) : "—"}
              </span>
            </div>
            <div className="bg-muted rounded h-1.5">
              <div className={`${color} h-full rounded`} style={{ width: `${v * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
