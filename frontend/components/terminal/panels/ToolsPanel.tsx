"use client";
import { useState } from "react";
import useSWR from "swr";
import { fxApi } from "@/lib/api";
import { BacktestForm } from "@/components/backtest/backtest-form";

type Tool = "backtest" | "position" | "fx" | "return";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-[var(--color-border)]/50">
      <span className="text-[12px] font-data text-[var(--color-text-secondary)] w-24 shrink-0">{label}</span>
      {children}
    </div>
  );
}

function CalcInput({
  value, onChange, placeholder, prefix,
}: { value: string; onChange: (v: string) => void; placeholder?: string; prefix?: string }) {
  return (
    <div className="flex items-center gap-1">
      {prefix && <span className="text-[12px] font-data text-[var(--color-text-muted)]">{prefix}</span>}
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-28 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded px-2 py-1 text-[13px] font-data text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)]"
      />
    </div>
  );
}

function Result({ label, value, color = "text-[var(--color-text-primary)]" }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/30">
      <span className="text-[12px] font-data text-[var(--color-text-secondary)]">{label}</span>
      <span className={`text-[14px] font-data font-medium ${color}`}>{value}</span>
    </div>
  );
}

function PositionCalc() {
  const [capital, setCapital] = useState("");
  const [riskPct, setRiskPct] = useState("2");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");

  const cap = parseFloat(capital) || 0;
  const risk = parseFloat(riskPct) || 0;
  const ent = parseFloat(entry) || 0;
  const stp = parseFloat(stop) || 0;

  const riskAmt = cap * (risk / 100);
  const slPct = ent > 0 && stp > 0 ? Math.abs((ent - stp) / ent) : 0;
  const shares = slPct > 0 ? Math.floor(riskAmt / (ent * slPct)) : 0;
  const posSize = shares * ent;
  const posPct = cap > 0 ? (posSize / cap) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Row label="자본금"><CalcInput value={capital} onChange={setCapital} placeholder="10000000" prefix="₩" /></Row>
        <Row label="리스크 %"><CalcInput value={riskPct} onChange={setRiskPct} placeholder="2" prefix="%" /></Row>
        <Row label="진입가"><CalcInput value={entry} onChange={setEntry} placeholder="75000" /></Row>
        <Row label="손절가"><CalcInput value={stop} onChange={setStop} placeholder="70000" /></Row>
      </div>
      <div className="pt-2 space-y-0.5">
        <Result label="리스크 금액" value={riskAmt > 0 ? `₩${riskAmt.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "—"} />
        <Result label="손절폭" value={slPct > 0 ? `${(slPct * 100).toFixed(2)}%` : "—"} />
        <Result label="매수 수량" value={shares > 0 ? `${shares.toLocaleString("ko-KR")}주` : "—"} color="text-[var(--color-primary)]" />
        <Result label="포지션 크기" value={posSize > 0 ? `₩${posSize.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "—"} />
        <Result label="자본 대비" value={posPct > 0 ? `${posPct.toFixed(1)}%` : "—"} />
      </div>
    </div>
  );
}

function FxCalc() {
  const { data: usdkrw, isLoading } = useSWR("/api/fx/USDKRW", () => fxApi.rate("USDKRW"));
  const [amount, setAmount] = useState("");
  const [dir, setDir] = useState<"usd2krw" | "krw2usd">("usd2krw");

  const rate = usdkrw?.rate ?? 0;
  const amt = parseFloat(amount) || 0;
  const converted = dir === "usd2krw" ? amt * rate : rate > 0 ? amt / rate : 0;

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Row label="환율 (USDKRW)">
          <span className="text-[14px] font-data text-[var(--color-primary)]">
            {isLoading ? "로딩…" : rate > 0 ? `₩${rate.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}` : "—"}
          </span>
        </Row>
        <Row label="방향">
          <div className="flex gap-3">
            {(["usd2krw", "krw2usd"] as const).map((d) => (
              <label key={d} className="flex items-center gap-1.5 cursor-pointer">
                <input type="radio" value={d} checked={dir === d} onChange={() => setDir(d)} className="accent-[var(--color-primary)]" />
                <span className="text-[12px] font-data text-[var(--color-text-secondary)]">
                  {d === "usd2krw" ? "USD → KRW" : "KRW → USD"}
                </span>
              </label>
            ))}
          </div>
        </Row>
        <Row label={dir === "usd2krw" ? "USD 금액"  : "KRW 금액"}>
          <CalcInput value={amount} onChange={setAmount} placeholder={dir === "usd2krw" ? "1000" : "1000000"} prefix={dir === "usd2krw" ? "$" : "₩"} />
        </Row>
      </div>
      <div className="pt-2 space-y-0.5">
        <Result
          label={dir === "usd2krw" ? "KRW 환산" : "USD 환산"}
          value={converted > 0 ? (dir === "usd2krw" ? `₩${converted.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : `$${converted.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`) : "—"}
          color="text-[var(--color-primary)]"
        />
      </div>
    </div>
  );
}

function ReturnCalc() {
  const [buyPrice, setBuyPrice] = useState("");
  const [sellPrice, setSellPrice] = useState("");
  const [qty, setQty] = useState("");
  const [feePct, setFeePct] = useState("0.015");

  const buy = parseFloat(buyPrice) || 0;
  const sell = parseFloat(sellPrice) || 0;
  const q = parseFloat(qty) || 0;
  const fee = parseFloat(feePct) || 0;

  const gross = (sell - buy) * q;
  const feeAmt = (buy * q + sell * q) * (fee / 100);
  const net = gross - feeAmt;
  const retPct = buy > 0 ? ((sell - buy) / buy) * 100 : 0;
  const netRetPct = buy * q > 0 ? (net / (buy * q)) * 100 : 0;

  const isProfit = net > 0;
  const color = net > 0 ? "text-[var(--color-gain)]" : net < 0 ? "text-[var(--color-loss)]" : "text-[var(--color-text-primary)]";

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Row label="매수가"><CalcInput value={buyPrice} onChange={setBuyPrice} placeholder="75000" /></Row>
        <Row label="매도가"><CalcInput value={sellPrice} onChange={setSellPrice} placeholder="82000" /></Row>
        <Row label="수량"><CalcInput value={qty} onChange={setQty} placeholder="100" /></Row>
        <Row label="수수료 %"><CalcInput value={feePct} onChange={setFeePct} placeholder="0.015" prefix="%" /></Row>
      </div>
      <div className="pt-2 space-y-0.5">
        <Result label="총 매수금액" value={buy * q > 0 ? `₩${(buy * q).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "—"} />
        <Result label="수익률" value={retPct !== 0 ? `${retPct >= 0 ? "+" : ""}${retPct.toFixed(2)}%` : "—"} color={color} />
        <Result label="수수료" value={feeAmt > 0 ? `₩${feeAmt.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "—"} />
        <Result label="순손익" value={net !== 0 ? `${isProfit ? "+" : ""}₩${net.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "—"} color={color} />
        <Result label="순수익률" value={netRetPct !== 0 ? `${netRetPct >= 0 ? "+" : ""}${netRetPct.toFixed(2)}%` : "—"} color={color} />
      </div>
    </div>
  );
}

const TABS: { id: Tool; label: string }[] = [
  { id: "backtest", label: "백테스트" },
  { id: "position", label: "포지션" },
  { id: "fx",       label: "환율"    },
  { id: "return",   label: "수익률"  },
];

export function ToolsPanel() {
  const [active, setActive] = useState<Tool>("backtest");

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 서브탭 헤더 */}
      <div className="flex items-stretch shrink-0 border-b border-[var(--color-border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={[
              "px-4 py-2 text-sm font-medium transition-colors",
              active === tab.id
                ? "text-[var(--color-primary)] border-b-2 border-[var(--color-primary)] -mb-px"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 콘텐츠 */}
      <div className="flex-1 overflow-auto p-4">
        {active === "backtest" && <BacktestForm />}
        {active === "position" && (
          <div className="max-w-sm">
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">포지션 사이즈 계산기</p>
            <PositionCalc />
          </div>
        )}
        {active === "fx" && (
          <div className="max-w-sm">
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">환율 변환기</p>
            <FxCalc />
          </div>
        )}
        {active === "return" && (
          <div className="max-w-sm">
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-3">수익률 계산기</p>
            <ReturnCalc />
          </div>
        )}
      </div>
    </div>
  );
}
