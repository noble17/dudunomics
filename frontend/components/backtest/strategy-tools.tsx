"use client";

import { useState } from "react";
import useSWR from "swr";
import { Calculator, DollarSign, Percent } from "lucide-react";
import { fxApi } from "@/lib/api";

function num(value: string) {
  return parseFloat(value) || 0;
}

function krw(value: number) {
  return value > 0 ? `₩${value.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}` : "-";
}

function Card({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <span className="text-primary">{icon}</span>
        <p className="text-sm font-semibold text-foreground">{title}</p>
      </div>
      <div className="space-y-3 p-4">{children}</div>
    </section>
  );
}

function Field({ label, value, onChange, prefix }: { label: string; value: string; onChange: (value: string) => void; prefix?: string }) {
  return (
    <label className="grid gap-1 text-xs text-muted-foreground">
      {label}
      <div className="flex h-9 items-center border border-border bg-background px-3 focus-within:border-primary">
        {prefix && <span className="mr-2 text-muted-foreground">{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent font-data text-sm text-foreground outline-none"
        />
      </div>
    </label>
  );
}

function Result({ label, value, color = "text-foreground" }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/70 py-2 last:border-b-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`font-data text-sm ${color}`}>{value}</span>
    </div>
  );
}

function PositionSizer() {
  const [capital, setCapital] = useState("");
  const [riskPct, setRiskPct] = useState("2");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const riskAmount = num(capital) * (num(riskPct) / 100);
  const stopLossPct = num(entry) > 0 && num(stop) > 0 ? Math.abs((num(entry) - num(stop)) / num(entry)) : 0;
  const shares = stopLossPct > 0 ? Math.floor(riskAmount / (num(entry) * stopLossPct)) : 0;
  const positionSize = shares * num(entry);

  return (
    <Card title="포지션 사이징" icon={<Calculator className="h-4 w-4" />}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="자본금" value={capital} onChange={setCapital} prefix="₩" />
        <Field label="리스크 %" value={riskPct} onChange={setRiskPct} />
        <Field label="진입가" value={entry} onChange={setEntry} />
        <Field label="손절가" value={stop} onChange={setStop} />
      </div>
      <div>
        <Result label="리스크 금액" value={krw(riskAmount)} />
        <Result label="손절폭" value={stopLossPct > 0 ? `${(stopLossPct * 100).toFixed(2)}%` : "-"} />
        <Result label="매수 수량" value={shares > 0 ? `${shares.toLocaleString("ko-KR")}주` : "-"} color="text-primary" />
        <Result label="포지션 크기" value={krw(positionSize)} />
      </div>
    </Card>
  );
}

function FxCalculator() {
  const { data } = useSWR("/api/fx/USDKRW", () => fxApi.rate("USDKRW"));
  const [amount, setAmount] = useState("");
  const [direction, setDirection] = useState<"usd2krw" | "krw2usd">("usd2krw");
  const rate = data?.rate ?? 0;
  const converted = direction === "usd2krw" ? num(amount) * rate : rate > 0 ? num(amount) / rate : 0;

  return (
    <Card title="환율 변환" icon={<DollarSign className="h-4 w-4" />}>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setDirection("usd2krw")}
          className={`flex-1 border px-3 py-2 text-xs ${direction === "usd2krw" ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground"}`}
        >
          USD → KRW
        </button>
        <button
          type="button"
          onClick={() => setDirection("krw2usd")}
          className={`flex-1 border px-3 py-2 text-xs ${direction === "krw2usd" ? "border-primary bg-primary text-primary-foreground" : "border-border text-muted-foreground"}`}
        >
          KRW → USD
        </button>
      </div>
      <Field label={direction === "usd2krw" ? "USD 금액" : "KRW 금액"} value={amount} onChange={setAmount} prefix={direction === "usd2krw" ? "$" : "₩"} />
      <div>
        <Result label="USDKRW" value={rate > 0 ? `₩${rate.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}` : "-"} />
        <Result
          label={direction === "usd2krw" ? "KRW 환산" : "USD 환산"}
          value={converted > 0 ? direction === "usd2krw" ? krw(converted) : `$${converted.toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "-"}
          color="text-primary"
        />
      </div>
    </Card>
  );
}

function ReturnCalculator() {
  const [buyPrice, setBuyPrice] = useState("");
  const [sellPrice, setSellPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [feePct, setFeePct] = useState("0.015");
  const gross = (num(sellPrice) - num(buyPrice)) * num(quantity);
  const fee = (num(buyPrice) * num(quantity) + num(sellPrice) * num(quantity)) * (num(feePct) / 100);
  const net = gross - fee;
  const returnPct = num(buyPrice) > 0 ? ((num(sellPrice) - num(buyPrice)) / num(buyPrice)) * 100 : 0;
  const color = net > 0 ? "text-gain" : net < 0 ? "text-loss" : "text-foreground";

  return (
    <Card title="수익률 계산" icon={<Percent className="h-4 w-4" />}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="매수가" value={buyPrice} onChange={setBuyPrice} />
        <Field label="매도가" value={sellPrice} onChange={setSellPrice} />
        <Field label="수량" value={quantity} onChange={setQuantity} />
        <Field label="수수료 %" value={feePct} onChange={setFeePct} />
      </div>
      <div>
        <Result label="총 매수금액" value={krw(num(buyPrice) * num(quantity))} />
        <Result label="수익률" value={returnPct !== 0 ? `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%` : "-"} color={color} />
        <Result label="수수료" value={krw(fee)} />
        <Result label="순손익" value={net !== 0 ? `${net >= 0 ? "+" : ""}${krw(Math.abs(net))}` : "-"} color={color} />
      </div>
    </Card>
  );
}

export function StrategyTools() {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-foreground">전략 도구</h2>
        <p className="mt-1 text-sm text-muted-foreground">포지션 사이징, 환율 변환, 수익률 계산을 한 곳에서 확인합니다.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <PositionSizer />
        <FxCalculator />
        <ReturnCalculator />
      </div>
    </section>
  );
}
