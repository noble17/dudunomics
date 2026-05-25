"use client";

import { useState, useEffect } from "react";
import { holdingsApi } from "@/lib/api";
import type { HoldingOut } from "@/lib/types";
import { HoldingsEditor } from "@/components/holdings/holdings-editor";

export default function HoldingsPage() {
  const [holdings, setHoldings] = useState<HoldingOut[]>([]);
  const [cash, setCash] = useState({ cash_krw: 0, cash_usd: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      holdingsApi.list().catch(() => [] as HoldingOut[]),
      holdingsApi.getCash().catch(() => ({ cash_krw: 0, cash_usd: 0 })),
    ]).then(([h, c]) => {
      setHoldings(h);
      setCash(c);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-muted-foreground">로딩 중…</div>;
  }

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
