"use client";

import { useState } from "react";
import useSWR from "swr";
import { Bot, ExternalLink, Newspaper, RotateCw } from "lucide-react";
import { aiApi, newsApi } from "@/lib/api";

interface Props {
  ticker: string;
}

function timeAgo(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "-";
  const diffMinutes = Math.floor((Date.now() - date.getTime()) / 60_000);
  if (diffMinutes < 60) return `${Math.max(diffMinutes, 0)}분 전`;
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}시간 전`;
  return `${Math.floor(diffMinutes / 1440)}일 전`;
}

export function TickerInsights({ ticker }: Props) {
  const { data: news, isLoading: newsLoading, mutate: refreshNews } = useSWR(
    ["news", ticker],
    () => newsApi.get(ticker, 8),
    { refreshInterval: 300_000, dedupingInterval: 60_000 },
  );
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const loadSummary = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const result = await aiApi.summary(ticker);
      setSummary(result.summary);
    } catch (error) {
      const message = error instanceof Error ? error.message : "AI 요약을 불러오지 못했습니다.";
      setSummaryError(message);
    } finally {
      setSummaryLoading(false);
    }
  };

  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="border border-border bg-card">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Newspaper className="h-4 w-4 text-primary" />
            <div>
              <p className="text-sm font-semibold text-foreground">뉴스</p>
              <p className="mt-1 text-xs text-muted-foreground">종목별 뉴스와 명시 실행형 AI 요약을 확인합니다.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => refreshNews()}
            className="inline-flex h-8 w-8 items-center justify-center border border-border bg-background text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            title="뉴스 새로고침"
          >
            <RotateCw className="h-4 w-4" />
          </button>
        </div>
        <div className="divide-y divide-border">
          {newsLoading ? (
            <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">뉴스를 불러오는 중입니다.</div>
          ) : !news?.items.length ? (
            <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">표시할 뉴스가 없습니다.</div>
          ) : (
            news.items.map((item) => (
              <a
                key={item.url || item.title}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-3 transition-colors hover:bg-[var(--secondary)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm leading-6 text-foreground">{item.title}</p>
                    <p className="mt-1 font-data text-xs text-muted-foreground">
                      {item.site || "News"} · {timeAgo(item.published_date)}
                    </p>
                  </div>
                  <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
                </div>
              </a>
            ))
          )}
        </div>
      </div>

      <div className="border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <div>
              <p className="text-sm font-semibold text-foreground">AI 요약</p>
              <p className="mt-1 text-xs text-muted-foreground">명시적으로 실행할 때만 AI API를 호출합니다.</p>
            </div>
          </div>
        </div>
        <div className="space-y-4 p-4">
          <button
            type="button"
            onClick={loadSummary}
            disabled={summaryLoading}
            className="inline-flex h-9 items-center gap-2 border border-primary bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {summaryLoading ? <RotateCw className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
            AI 요약 실행
          </button>
          {summaryError && (
            <p className="border border-loss/40 bg-loss/10 px-3 py-2 text-xs text-loss">{summaryError}</p>
          )}
          {summary ? (
            <p className="whitespace-pre-wrap text-sm leading-7 text-foreground">{summary}</p>
          ) : (
            <p className="text-sm leading-7 text-muted-foreground">
              최근 뉴스 기반으로 {ticker}의 시장 흐름을 짧게 요약합니다. API 키가 없거나 한도에 걸리면 오류를 그대로 보여줍니다.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
