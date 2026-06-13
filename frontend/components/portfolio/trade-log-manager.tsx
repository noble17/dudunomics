"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { FileUp, RefreshCw, Trash2, X } from "lucide-react";
import { tradesApi } from "@/lib/api";
import type { TradeImportPreview, TradeImportRow, TradeIn } from "@/lib/types";

const emptyForm: TradeIn = {
  ticker: "",
  trade_type: "BUY",
  quantity: 0,
  price: 0,
  currency: "USD",
  traded_at: new Date().toISOString().slice(0, 10),
};

export function TradeLogManager() {
  const { data: trades = [], mutate, isLoading } = useSWR("/api/trades", () => tradesApi.list(), { refreshInterval: 30_000 });
  const [form, setForm] = useState<TradeIn>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [savingImport, setSavingImport] = useState(false);
  const [preview, setPreview] = useState<TradeImportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = async () => {
    if (!form.ticker.trim() || form.quantity <= 0 || form.price <= 0) {
      setError("티커, 수량, 단가를 입력하세요.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await tradesApi.create({ ...form, ticker: form.ticker.trim().toUpperCase() });
      setForm({ ...emptyForm, traded_at: new Date().toISOString().slice(0, 10) });
      setMessage("수동 거래를 저장했습니다.");
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "거래 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await tradesApi.delete(id);
      setMessage("거래를 삭제했습니다.");
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "거래 삭제에 실패했습니다.");
    }
  };

  const syncToss = async () => {
    setSyncing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await tradesApi.syncFromToss();
      if (result.errors.length > 0) {
        setError(result.errors.join("\n"));
      } else if (result.added === 0) {
        setMessage("Toss API에서 새 진행 중/부분 체결 주문이 없습니다. 과거 체결 내역은 Toss PDF 가져오기로 저장하세요.");
      } else {
        setMessage(`Toss API 진행 중 주문 체결분 ${result.added}건을 추가했습니다.`);
      }
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toss 거래내역 동기화에 실패했습니다.");
    } finally {
      setSyncing(false);
    }
  };

  const updatePreviewRow = (rowId: string, patch: Partial<TradeImportRow>) => {
    setPreview((current) => current ? {
      ...current,
      rows: current.rows.map((row) => row.row_id === rowId ? { ...row, ...patch } : row),
    } : current);
  };

  const previewTossPdf = async (file?: File) => {
    if (!file) return;
    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await tradesApi.previewTossPdf(file);
      setPreview(result);
      const unresolved = result.rows.filter((row) => !row.ticker.trim()).length;
      setMessage(
        unresolved > 0
          ? `PDF에서 거래 ${result.rows.length}건을 읽었습니다. 자동 추천이 안 된 해외 종목 ${unresolved}건만 입력하세요.`
          : `PDF에서 거래 ${result.rows.length}건을 읽었고 티커를 자동 추천했습니다. 확인 후 저장하세요.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toss PDF 파싱에 실패했습니다.");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const commitTossPdf = async () => {
    if (!preview) return;
    const missing = preview.rows.filter((row) => !row.ticker.trim());
    if (missing.length > 0) {
      setError(`티커가 비어 있는 해외 거래 ${missing.length}건을 먼저 입력하세요.`);
      return;
    }
    setSavingImport(true);
    setError(null);
    try {
      const result = await tradesApi.commitTossPdf({
        ...preview,
        rows: preview.rows.map((row) => ({ ...row, ticker: row.ticker.trim().toUpperCase() })),
      });
      if (result.errors.length > 0) {
        setError(result.errors.join("\n"));
      }
      setMessage(`Toss PDF 거래 ${result.added}건을 저장했습니다.`);
      setPreview(null);
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toss PDF 거래 저장에 실패했습니다.");
    } finally {
      setSavingImport(false);
    }
  };

  return (
    <section className="border border-border bg-card">
      <div className="border-b border-border px-5 py-3">
        <p className="text-sm font-semibold text-foreground">거래 기록</p>
        <p className="mt-1 text-xs text-muted-foreground">
          과거 거래는 Toss PDF로 가져오고, Toss API 버튼은 현재 진행 중/부분 체결 주문만 확인합니다.
        </p>
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            <label className="grid gap-1 text-xs text-muted-foreground">
              티커
              <input
                value={form.ticker}
                onChange={(event) => setForm((prev) => ({ ...prev, ticker: event.target.value.toUpperCase() }))}
                className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
                placeholder="AAPL"
              />
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              거래
              <select
                value={form.trade_type}
                onChange={(event) => setForm((prev) => ({ ...prev, trade_type: event.target.value as "BUY" | "SELL" }))}
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              수량
              <input
                type="number"
                value={form.quantity || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, quantity: parseFloat(event.target.value) || 0 }))}
                className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              단가
              <input
                type="number"
                value={form.price || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, price: parseFloat(event.target.value) || 0 }))}
                className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              통화
              <select
                value={form.currency}
                onChange={(event) => setForm((prev) => ({ ...prev, currency: event.target.value as "KRW" | "USD" }))}
                className="h-9 border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary"
              >
                <option value="USD">USD</option>
                <option value="KRW">KRW</option>
              </select>
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              거래일
              <input
                type="date"
                value={form.traded_at}
                onChange={(event) => setForm((prev) => ({ ...prev, traded_at: event.target.value }))}
                className="h-9 border border-border bg-background px-3 font-data text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
          </div>
          {error && <p className="border border-loss/40 bg-loss/10 px-3 py-2 text-xs text-loss">{error}</p>}
          {message && <p className="border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">{message}</p>}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => previewTossPdf(event.target.files?.[0])}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="inline-flex h-9 w-full items-center justify-center gap-2 border border-border bg-background px-3 text-sm font-medium text-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileUp className="h-4 w-4" />
            {importing ? "PDF 읽는 중" : "Toss PDF 가져오기"}
          </button>
          <button
            type="button"
            onClick={syncToss}
            disabled={syncing}
            className="inline-flex h-9 w-full items-center justify-center gap-2 border border-border bg-background px-3 text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Toss API 확인 중" : "Toss API 진행 중 주문 확인"}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={saving}
            className="inline-flex h-9 w-full items-center justify-center border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "저장 중" : "거래 추가"}
          </button>
        </div>

        <div className="overflow-x-auto border border-border">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-border bg-muted/30">
              <tr>
                {["거래일", "구분", "티커", "수량", "단가", "통화", "출처", ""].map((header) => (
                  <th key={header} className="px-3 py-3 text-right text-[11px] font-medium text-muted-foreground first:text-left">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={8} className="px-3 py-8 text-center text-xs text-muted-foreground">거래 기록을 불러오는 중입니다.</td></tr>
              ) : trades.length === 0 ? (
                <tr><td colSpan={8} className="px-3 py-8 text-center text-xs text-muted-foreground">거래 내역이 없습니다.</td></tr>
              ) : (
                trades.map((trade) => (
                  <tr key={trade.id} className="border-b border-border last:border-0 hover:bg-[var(--secondary)]">
                    <td className="px-3 py-2 font-data text-xs text-muted-foreground">{trade.traded_at}</td>
                    <td className={`px-3 py-2 text-right font-data ${trade.trade_type === "BUY" ? "text-gain" : "text-loss"}`}>{trade.trade_type}</td>
                    <td className="px-3 py-2 text-right font-data text-foreground">{trade.ticker}</td>
                    <td className="px-3 py-2 text-right font-data">{trade.quantity}</td>
                    <td className="px-3 py-2 text-right font-data">{trade.price.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right font-data text-muted-foreground">{trade.currency}</td>
                    <td className="px-3 py-2 text-right font-data text-muted-foreground">
                      <span className="border border-border px-2 py-1 text-[11px]">{trade.source ?? "manual"}</span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      {(trade.source ?? "manual") === "manual" ? (
                        <button
                          type="button"
                          onClick={() => remove(trade.id)}
                          className="inline-flex h-8 w-8 items-center justify-center border border-border text-muted-foreground hover:border-loss hover:text-loss"
                          title="거래 삭제"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">읽기전용</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {preview && (
        <div className="border-t border-border p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Toss PDF 미리보기</p>
              <p className="mt-1 text-xs text-muted-foreground">
                국내 거래는 자동 매핑하고, 해외 거래는 ISIN으로 티커를 자동 추천합니다. 비어 있는 행만 확인해 주세요.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="inline-flex h-8 items-center gap-1 border border-border px-3 text-xs text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
                닫기
              </button>
              <button
                type="button"
                onClick={commitTossPdf}
                disabled={savingImport}
                className="h-8 border border-primary bg-primary px-3 text-xs font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
              >
                {savingImport ? "저장 중" : `${preview.rows.length}건 저장`}
              </button>
            </div>
          </div>
          {preview.errors.length > 0 && (
            <p className="mb-3 border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-200">
              일부 행은 건너뛰었습니다: {preview.errors.slice(0, 3).join(" · ")}
              {preview.errors.length > 3 ? ` 외 ${preview.errors.length - 3}건` : ""}
            </p>
          )}
          <div className="max-h-[360px] overflow-auto border border-border">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="sticky top-0 border-b border-border bg-card">
                <tr>
                  {["거래일", "구분", "종목명", "원본코드", "티커", "수량", "단가", "통화", "수수료"].map((header) => (
                    <th key={header} className="px-3 py-2 text-right text-[11px] font-medium text-muted-foreground first:text-left">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.row_id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 font-data text-xs text-muted-foreground">{row.traded_at}</td>
                    <td className={`px-3 py-2 text-right font-data ${row.trade_type === "BUY" ? "text-gain" : "text-loss"}`}>{row.trade_type}</td>
                    <td className="px-3 py-2 text-right text-foreground">{row.name ?? "-"}</td>
                    <td className="px-3 py-2 text-right font-data text-muted-foreground">{row.raw_symbol ?? "-"}</td>
                    <td className="px-3 py-2 text-right">
                      <input
                        value={row.ticker}
                        onChange={(event) => updatePreviewRow(row.row_id, { ticker: event.target.value.toUpperCase(), needs_mapping: false })}
                        className={`h-8 w-32 border bg-background px-2 text-right font-data text-xs text-foreground outline-none focus:border-primary ${
                          row.needs_mapping && !row.ticker ? "border-amber-500/60" : "border-border"
                        }`}
                        placeholder={row.needs_mapping ? "예: AMZN" : ""}
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-data">{row.quantity.toLocaleString("ko-KR")}</td>
                    <td className="px-3 py-2 text-right font-data">{row.price.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}</td>
                    <td className="px-3 py-2 text-right font-data text-muted-foreground">{row.currency}</td>
                    <td className="px-3 py-2 text-right font-data text-muted-foreground">{(row.fee ?? 0).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
