// frontend/components/backtest/backtest-form.tsx
"use client";

import { useState } from "react";
import useSWR from "swr";
import { backtestApi } from "@/lib/api";
import type { BacktestRunOut, StrategyDef } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BacktestResult } from "./backtest-result";

export function BacktestForm() {
  const { data: strategies } = useSWR("/api/backtest/strategies", backtestApi.strategies);

  const [ticker, setTicker] = useState("005930.KS");
  const [strategy, setStrategy] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 3); return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [params, setParams] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestRunOut | null>(null);
  const [error, setError] = useState("");

  const selectedStrategy: StrategyDef | undefined =
    strategies?.find((s) => s.name === strategy) ?? strategies?.[0];

  const run = async () => {
    if (!selectedStrategy) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const parsedParams = Object.fromEntries(
        Object.entries(selectedStrategy.params_schema).map(([k, schema]) => [
          k, parseFloat(params[k] ?? String(schema.default)),
        ])
      );
      const res = await backtestApi.run({
        ticker,
        strategy: selectedStrategy.name,
        params: parsedParams,
        period_start: startDate,
        period_end: endDate,
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle className="text-base">파라미터 설정</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <Label>티커 (yfinance)</Label>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="005930.KS" />
            </div>
            <div className="space-y-1">
              <Label>전략</Label>
              <Select value={strategy || selectedStrategy?.name || ""}
                onValueChange={(v) => setStrategy(v ?? "")}>
                <SelectTrigger><SelectValue placeholder="전략 선택" /></SelectTrigger>
                <SelectContent>
                  {strategies?.map((s) => (
                    <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>시작일</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>종료일</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          {selectedStrategy && (
            <div className="flex flex-wrap gap-4">
              {Object.entries(selectedStrategy.params_schema).map(([k, schema]) => (
                <div key={k} className="space-y-1">
                  <Label>{schema.label}</Label>
                  <Input
                    type="number"
                    value={params[k] ?? String(schema.default)}
                    onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                    min={schema.min} max={schema.max}
                    className="w-24"
                  />
                </div>
              ))}
            </div>
          )}

          <Button onClick={run} disabled={running || !strategies}>
            {running ? "실행 중…" : "백테스트 실행"}
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && <BacktestResult result={result} />}
    </div>
  );
}
