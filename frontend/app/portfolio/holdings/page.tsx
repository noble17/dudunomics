"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { holdingsApi } from "@/lib/api";
import type { CashOut, HoldingOut } from "@/lib/types";
import { HoldingsEditor } from "@/components/holdings/holdings-editor";
import { TradeLogManager } from "@/components/portfolio/trade-log-manager";

export default function PortfolioHoldingsPage() {
  const [holdings, setHoldings] = useState<HoldingOut[]>([]);
  const [cash, setCash] = useState<CashOut>({ cash_krw: 0, cash_usd: 0 });
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    Promise.all([
      holdingsApi.list().catch(() => [] as HoldingOut[]),
      holdingsApi.getCash().catch(() => ({ cash_krw: 0, cash_usd: 0 } as CashOut)),
    ]).then(([h, c]) => {
      setHoldings(h);
      setCash(c);
      setLoading(false);
    });
  };

  useEffect(() => {
    reload();
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-muted-foreground">로딩 중...</div>;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/portfolio"
            className="inline-flex items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            포트폴리오로 돌아가기
          </Link>
          <h1 className="mt-3 font-heading text-2xl font-bold tracking-tight">보유종목 관리</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Toss 동기화 데이터와 수동 입력 데이터를 source별로 관리합니다.
          </p>
        </div>
      </header>
      <HoldingsEditor
        initialHoldings={holdings}
        initialCashKrw={cash.cash_krw}
        initialCashUsd={cash.cash_usd}
        cashSources={cash.sources ?? []}
        totalCashKrw={cash.total_cash_krw ?? cash.cash_krw}
        totalCashUsd={cash.total_cash_usd ?? cash.cash_usd}
        onReload={reload}
      />
      <TradeLogManager />
    </div>
  );
}
