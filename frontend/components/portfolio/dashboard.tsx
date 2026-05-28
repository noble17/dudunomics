// frontend/components/portfolio/dashboard.tsx
"use client";

import type { PortfolioRow, PortfolioSnapshot, SnapshotHistory } from "@/lib/types";
import { KpiCard, type KpiCardProps } from "@/components/common/kpi-card";
import { WeightPie } from "./weight-pie";
import { ReturnBar } from "./return-bar";
import { EquityCurve } from "./equity-curve";

interface Props {
  snapshot: PortfolioSnapshot;
  history: SnapshotHistory[];
}

const LABEL = "text-[11px] font-medium text-muted-foreground";

function fmt(n: number) {
  return `₩${Math.abs(n).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
}

function fmtSign(n: number) {
  return `${n >= 0 ? "+" : "−"}${fmt(n)}`;
}

function fmtPct(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}


function SectionHeader({ title }: { title: string }) {
  return (
    <div className="border-b border-border px-5 py-3">
      <p className={LABEL}>{title}</p>
    </div>
  );
}

function inferMarket(ticker: string): string {
  if (ticker.endsWith(".KS")) return "KOSPI";
  if (ticker.endsWith(".KQ")) return "KOSDAQ";
  return "";
}

function MarketBadge({ label }: { label: string }) {
  if (!label) return <span className="text-muted-foreground font-mono text-xs">—</span>;
  return (
    <span className="border border-border px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-muted-foreground">
      {label}
    </span>
  );
}

function HoldingsTable({ rows, usdkrw }: { rows: PortfolioRow[]; usdkrw: number }) {
  const isKrw = rows[0]?.currency === "KRW";

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-[#F9FAFC]">
          <tr>
            {["종목명", "시장", "섹터", "보유", "평균단가", "현재가", "매입액", "평가액", "평가손익", "수익률"].map((h) => (
              <th
                key={h}
                className={`px-4 py-3 font-normal ${LABEL} text-right first:text-left`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const costOrig = row.avg_price * row.quantity;
            const costKrw = isKrw ? costOrig : costOrig * usdkrw;
            const pnlKrw = row.market_value_krw - costKrw;
            const pnlOrig = isKrw ? pnlKrw : pnlKrw / usdkrw;
            const marketValueOrig = isKrw ? row.market_value_krw : row.market_value_krw / usdkrw;
            const pnlClass = pnlKrw >= 0 ? "text-gain" : "text-loss";
            const retClass = row.return_pct >= 0 ? "text-gain" : "text-loss";
            const market = inferMarket(row.ticker);

            return (
              <tr key={row.ticker} className="border-b border-border last:border-0 hover:bg-[#F4F5F7]">
                {/* 종목명 + 티커 서브텍스트 */}
                <td className="px-4 py-2">
                  <p className="font-data text-foreground">{row.name || row.ticker}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{row.ticker}</p>
                </td>
                {/* 시장 */}
                <td className="px-4 py-2"><MarketBadge label={market} /></td>
                {/* 섹터 */}
                <td className="px-4 py-2">
                  {row.sector
                    ? <span className="border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">{row.sector}</span>
                    : <span className="text-muted-foreground font-mono text-xs">—</span>
                  }
                </td>
                {/* 보유 */}
                <td className="px-4 py-2 font-data text-right">{row.quantity.toLocaleString()}</td>
                {/* 평균단가 */}
                <td className="px-4 py-2 font-data text-right text-muted-foreground">
                  {isKrw ? `₩${row.avg_price.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : `$${row.avg_price.toFixed(2)}`}
                </td>
                {/* 현재가 */}
                <td className="px-4 py-2 font-data text-right">
                  {isKrw ? `₩${row.current_price.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : `$${row.current_price.toFixed(2)}`}
                </td>
                {/* 매입액 */}
                <td className="px-4 py-2 font-data text-right text-muted-foreground">
                  {isKrw ? `₩${costOrig.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : `$${costOrig.toFixed(2)}`}
                </td>
                {/* 평가액 */}
                <td className="px-4 py-2 font-data text-right">
                  <p>₩{row.market_value_krw.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</p>
                  {!isKrw && (
                    <p className="text-[10px] text-muted-foreground">${marketValueOrig.toFixed(2)}</p>
                  )}
                </td>
                {/* 평가손익 */}
                <td className={`px-4 py-2 font-data text-right ${pnlClass}`}>
                  <p>{pnlKrw >= 0 ? "+" : "−"}₩{Math.abs(pnlKrw).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}</p>
                  {!isKrw && (
                    <p className="text-[10px]">{pnlOrig >= 0 ? "+" : "−"}${Math.abs(pnlOrig).toFixed(2)}</p>
                  )}
                </td>
                {/* 수익률 */}
                <td className={`px-4 py-2 font-data text-right ${retClass}`}>
                  {fmtPct(row.return_pct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PortfolioDashboard({ snapshot, history }: Props) {
  const { rows, total_equity_krw, total_with_cash_krw, cash_krw, cash_usd, usdkrw, updated_at } = snapshot;

  const krRows = rows.filter((r) => r.currency === "KRW");
  const usRows = rows.filter((r) => r.currency === "USD");

  const krEquity = krRows.reduce((s, r) => s + r.market_value_krw, 0);
  const usEquity = usRows.reduce((s, r) => s + r.market_value_krw, 0);

  const krCost = krRows.reduce((s, r) => s + r.avg_price * r.quantity, 0);
  const usCost = usRows.reduce((s, r) => s + r.avg_price * r.quantity * usdkrw, 0);
  const totalCost = krCost + usCost;

  const krPnl = krEquity - krCost;
  const usPnl = usEquity - usCost;
  // cash_krw는 API에서 이미 KRW+USD*환율 합산된 총액
  const totalCash = cash_krw;
  const totalReturn = totalCost > 0 ? ((total_equity_krw - totalCost) / totalCost) * 100 : 0;

  const kpis: KpiCardProps[] = [
    { label: "순자산", value: fmt(total_with_cash_krw) },
    { label: "수익률", value: fmtPct(totalReturn), sub: fmtSign(total_equity_krw - totalCost), colored: true, positive: totalReturn >= 0 },
    { label: "현금", value: fmt(totalCash) },
    { label: "국내평가금액", value: fmt(krEquity) },
    { label: "해외평가금액", value: fmt(usEquity) },
    {
      label: "국내손익",
      value: fmtSign(krPnl),
      colored: true,
      positive: krPnl >= 0,
    },
    {
      label: "해외손익",
      value: fmtSign(usPnl),
      colored: true,
      positive: usPnl >= 0,
    },
  ];

  return (
    <div className="space-y-6">
      {/* 7 KPI 카드 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      {/* 비중 도넛 + 종목별 수익률 바 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="border border-border bg-card p-5">
          <p className={`${LABEL} mb-3`}>비중</p>
          <WeightPie rows={rows} cashKrw={totalCash} />
        </div>
        <div className="border border-border bg-card p-5">
          <p className={`${LABEL} mb-3`}>종목별 수익률</p>
          <ReturnBar rows={rows} />
        </div>
      </div>

      {/* 자산 추이 (2 라인) */}
      <div className="border border-border bg-card p-5">
        <p className={`${LABEL} mb-3`}>자산 추이</p>
        <EquityCurve history={history} />
      </div>

      {/* 국내 종목 테이블 */}
      <div className="border border-border bg-card">
        <SectionHeader title="국내 종목" />
        {krRows.length > 0 ? (
          <HoldingsTable rows={krRows} usdkrw={usdkrw} />
        ) : (
          <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
            보유 종목 없음 — 보유종목 페이지에서 추가하세요
          </div>
        )}
      </div>

      {/* 해외 종목 테이블 */}
      <div className="border border-border bg-card">
        <SectionHeader title="해외 종목" />
        {usRows.length > 0 ? (
          <HoldingsTable rows={usRows} usdkrw={usdkrw} />
        ) : (
          <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">
            보유 종목 없음 — 보유종목 페이지에서 추가하세요
          </div>
        )}
      </div>

      <p className="text-right font-mono text-xs text-muted-foreground">
        마지막 갱신: {new Date(updated_at).toLocaleString("ko-KR")} · USD/KRW {usdkrw.toLocaleString("ko-KR")}
      </p>
    </div>
  );
}
