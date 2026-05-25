export const dynamic = "force-dynamic";

import { holdingsApi } from "@/lib/api";
import { HoldingsEditor } from "@/components/holdings/holdings-editor";

export default async function HoldingsPage() {
  const [holdings, cash] = await Promise.all([
    holdingsApi.list().catch(() => []),
    holdingsApi.getCash().catch(() => ({ cash_krw: 0, cash_usd: 0 })),
  ]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">보유종목 편집</h1>
      <HoldingsEditor
        initialHoldings={holdings}
        initialCashKrw={cash.cash_krw}
        initialCashUsd={cash.cash_usd}
      />
    </div>
  );
}
