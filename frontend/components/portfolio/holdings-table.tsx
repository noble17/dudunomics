// frontend/components/portfolio/holdings-table.tsx
import type { PortfolioRow } from "@/lib/types";

interface Props { rows: PortfolioRow[]; currency: "KRW" | "USD"; usdkrw: number }

export function HoldingsTable({ rows, currency, usdkrw }: Props) {
  const sym = currency === "KRW" ? "₩" : "$";
  const convert = (krw: number) => currency === "KRW" ? krw : krw / usdkrw;

  return (
    <div className="overflow-x-auto border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-[#F9FAFC]">
          <tr>
            {["티커", "종목명", "수량", "평균단가", "현재가", "평가금액", "수익률", "비중"].map((h) => (
              <th key={h} className="px-4 py-3 text-right text-[11px] font-medium text-muted-foreground first:text-left">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker} className="border-b border-border last:border-0 hover:bg-[#F4F5F7]">
              <td className="font-data px-4 py-3 font-bold text-foreground">{r.ticker}</td>
              <td className="px-4 py-3 text-right text-muted-foreground">{r.name}</td>
              <td className="font-data px-4 py-3 text-right">{r.quantity.toLocaleString()}</td>
              <td className="font-data px-4 py-3 text-right">{r.avg_price.toLocaleString()}</td>
              <td className="font-data px-4 py-3 text-right">{r.current_price.toLocaleString()}</td>
              <td className="font-data px-4 py-3 text-right font-medium">
                {sym}{convert(r.market_value_krw).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
              </td>
              <td className="font-data px-4 py-3 text-right">
                <span className={r.return_pct >= 0 ? "text-gain" : "text-loss"}>
                  {r.return_pct >= 0 ? "+" : ""}{r.return_pct.toFixed(2)}%
                </span>
              </td>
              <td className="font-data px-4 py-3 text-right text-muted-foreground">{r.weight_pct.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
