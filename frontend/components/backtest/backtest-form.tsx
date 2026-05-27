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

  const [tickerInput, setTickerInput] = useState("005930.KS");
  const [strategy, setStrategy] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 3); return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [params, setParams] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestRunOut | null>(null);
  const [error, setError] = useState("");
  const [weighting, setWeighting] = useState<"equal" | "inverse_vol">("equal");
  const [marketFilter, setMarketFilter] = useState(false);
  const [mfIndex, setMfIndex] = useState<"auto" | "spy" | "kospi">("auto");

  const selectedStrategy: StrategyDef | undefined =
    strategies?.find((s) => s.name === strategy) ?? strategies?.[0];

  const tickers = tickerInput.split(",").map((t) => t.trim()).filter(Boolean);

  const run = async () => {
    if (!selectedStrategy || tickers.length === 0) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const parsedParams = Object.fromEntries(
        Object.entries(selectedStrategy.params_schema).map(([k, schema]) => {
          const raw = params[k] ?? String(schema.default);
          return [k, schema.type === "enum" ? raw : parseFloat(raw)];
        })
      );
      const res = await backtestApi.run({
        tickers,
        strategy: selectedStrategy.name,
        params: parsedParams,
        period_start: startDate,
        period_end: endDate,
        ...(selectedStrategy.supports_risk_options ? {
          risk_options: {
            weighting,
            market_filter: marketFilter,
            market_filter_index: mfIndex,
          }
        } : {}),
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
            <div className="space-y-1 sm:col-span-2 lg:col-span-1">
              <Label>종목 (쉼표로 구분)</Label>
              <Input value={tickerInput} onChange={(e) => setTickerInput(e.target.value)} placeholder="AAPL, MSFT, NVDA" />
            </div>
            <div className="space-y-1">
              <Label>전략</Label>
              <Select value={strategy || selectedStrategy?.name || ""}
                onValueChange={(v) => setStrategy(v ?? "")}>
                <SelectTrigger><SelectValue placeholder="전략 선택" /></SelectTrigger>
                <SelectContent>
                  {strategies?.map((s) => (
                    <SelectItem key={s.name} value={s.name}>
                      <div className="flex items-center gap-2 py-0.5">
                        {s.icon && <span className="text-base leading-none">{s.icon}</span>}
                        <div className="flex flex-col">
                          <span className="text-[13px] font-medium">{s.name}</span>
                          {s.description && (
                            <span className="text-[11px] text-muted-foreground leading-tight">{s.description}</span>
                          )}
                        </div>
                        {s.tags?.[0] && (
                          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground shrink-0">
                            {s.tags[0]}
                          </span>
                        )}
                      </div>
                    </SelectItem>
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

          {selectedStrategy?.description && (
            <div className="rounded-lg border bg-muted/30 p-3 flex items-start gap-3">
              {selectedStrategy.icon && (
                <span className="text-2xl leading-none mt-0.5">{selectedStrategy.icon}</span>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[13px] font-semibold">{selectedStrategy.name}</span>
                  {selectedStrategy.tags?.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  {selectedStrategy.description}
                </p>
              </div>
            </div>
          )}

          {selectedStrategy && Object.keys(selectedStrategy.params_schema).length > 0 && (
            <div className="flex flex-wrap gap-4">
              {Object.entries(selectedStrategy.params_schema).map(([k, schema]) => (
                <div key={k} className="space-y-1">
                  <Label>{schema.label}</Label>
                  {schema.type === "enum" ? (
                    <Select
                      value={params[k] ?? String(schema.default)}
                      onValueChange={(v) => setParams((p) => ({ ...p, [k]: v ?? String(schema.default) }))}
                    >
                      <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {schema.options?.map((opt) => (
                          <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type="number"
                      value={params[k] ?? String(schema.default)}
                      onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                      min={schema.min}
                      max={schema.max}
                      step={schema.type === "float" ? 0.01 : 1}
                      className="w-24"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {selectedStrategy?.supports_risk_options && (
            <Card>
              <CardContent className="pt-4">
                <p className="mb-3 text-[11px] font-medium text-muted-foreground">리스크 옵션</p>
                <div className="space-y-3">
                  {/* 자산 배분 방식 */}
                  <div className="space-y-1">
                    <Label className="text-[11px]">자산 배분 방식</Label>
                    <div className="flex gap-4">
                      {(["equal", "inverse_vol"] as const).map((v) => (
                        <label key={v} className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            value={v}
                            checked={weighting === v}
                            onChange={() => setWeighting(v)}
                            className="accent-primary"
                          />
                          <span className="text-[12px]">{v === "equal" ? "동일 비중" : "역변동성 비중"}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  {/* 마켓 필터 */}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="market-filter"
                      checked={marketFilter}
                      onChange={(e) => setMarketFilter(e.target.checked)}
                      className="accent-primary"
                    />
                    <Label htmlFor="market-filter" className="text-[12px] cursor-pointer">
                      마켓 필터 (시장 200일 MA 이탈 시 주식 비중 50% 축소)
                    </Label>
                  </div>
                  {/* 지수 선택 (마켓 필터 활성 시만) */}
                  {marketFilter && (
                    <div className="space-y-1">
                      <Label className="text-[11px]">기준 지수</Label>
                      <Select value={mfIndex} onValueChange={(v) => setMfIndex(v as "auto" | "spy" | "kospi")}>
                        <SelectTrigger className="w-36 h-8 text-[12px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="auto">Auto (자동 감지)</SelectItem>
                          <SelectItem value="spy">SPY (미국)</SelectItem>
                          <SelectItem value="kospi">KOSPI (한국)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <Button onClick={run} disabled={running || !strategies || tickers.length === 0}>
            {running ? "실행 중…" : "백테스트 실행"}
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && <BacktestResult result={result} />}
    </div>
  );
}
