// frontend/components/portfolio/holdings-table.tsx
import { Badge } from "@/components/ui/badge";
import type { PortfolioRow } from "@/lib/types";

interface Props { rows: PortfolioRow[]; currency: "KRW" | "USD"; usdkrw: number }

export function HoldingsTable({ rows, currency, usdkrw }: Props) {
  const sym = currency === "KRW" ? "₩" : "$";
  const convert = (krw: number) => currency === "KRW" ? krw : krw / usdkrw;

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="w-full text-sm">
        <thead className="border-b bg-slate-50 text-xs uppercase text-muted-foreground">
          <tr>
            {["티커","종목명","수량","평균단가","현재가","평가금액","수익률","비중"].map((h) => (
              <th key={h} className="px-4 py-3 text-right first:text-left">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker} className="border-b last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 font-mono font-medium">{r.ticker}</td>
              <td className="px-4 py-3 text-right text-muted-foreground">{r.name}</td>
              <td className="px-4 py-3 text-right">{r.quantity.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{r.avg_price.toLocaleString()}</td>
              <td className="px-4 py-3 text-right">{r.current_price.toLocaleString()}</td>
              <td className="px-4 py-3 text-right font-medium">
                {sym}{convert(r.market_value_krw).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
              </td>
              <td className="px-4 py-3 text-right">
                <Badge variant={r.return_pct >= 0 ? "default" : "destructive"}
                  className={r.return_pct >= 0 ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-100" : ""}>
                  {r.return_pct >= 0 ? "+" : ""}{r.return_pct.toFixed(2)}%
                </Badge>
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">{r.weight_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
