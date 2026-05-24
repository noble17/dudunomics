// frontend/components/portfolio/kpi-cards.tsx
import { Card, CardContent } from "@/components/ui/card";
import type { PortfolioSnapshot } from "@/lib/types";

interface Props {
  snapshot: PortfolioSnapshot;
  currency: "KRW" | "USD";
  weightMode: "equity" | "total";
}

function fmt(val: number, currency: string) {
  const sym = currency === "KRW" ? "₩" : "$";
  return `${sym}${val.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
}

export function KpiCards({ snapshot, currency, weightMode }: Props) {
  const usdkrw = snapshot.usdkrw;
  const toDisplay = (krw: number) =>
    currency === "KRW" ? krw : krw / usdkrw;

  const equity = toDisplay(snapshot.total_equity_krw);
  const withCash = toDisplay(snapshot.total_with_cash_krw);
  const cash = toDisplay(snapshot.cash_krw);

  const items = [
    { label: "주식 평가액", value: fmt(equity, currency) },
    { label: "현금 포함", value: fmt(withCash, currency) },
    { label: "현금", value: fmt(cash, currency) },
    { label: "USD/KRW", value: `₩${usdkrw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
