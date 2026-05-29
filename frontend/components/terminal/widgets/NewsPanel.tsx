"use client";
import useSWR from "swr";
import { newsApi } from "@/lib/api";
import type { NewsItem } from "@/lib/types";

interface Props {
  ticker: string;
}

function timeAgo(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const diff = Math.floor((Date.now() - d.getTime()) / 60000);
  if (diff < 60) return `${diff}분 전`;
  if (diff < 1440) return `${Math.floor(diff / 60)}시간 전`;
  return `${Math.floor(diff / 1440)}일 전`;
}

function NewsCard({ item }: { item: NewsItem }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-3 py-2 border-b border-[var(--color-border)] hover:bg-[var(--color-bg-hover)] transition-colors cursor-pointer"
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-mono text-[var(--color-text-primary)] leading-tight line-clamp-2">
            {item.title}
          </p>
          <p className="text-[9px] font-mono text-[var(--color-text-muted)] mt-0.5">
            {item.site} · {timeAgo(item.published_date)}
          </p>
        </div>
      </div>
    </a>
  );
}

function SkeletonCard() {
  return (
    <div className="px-3 py-2 border-b border-[var(--color-border)]">
      <div className="h-3 bg-[var(--color-bg-hover)] rounded w-3/4 mb-1 animate-pulse" />
      <div className="h-2 bg-[var(--color-bg-hover)] rounded w-1/3 animate-pulse" />
    </div>
  );
}

export function NewsPanel({ ticker }: Props) {
  const { data, isLoading, error } = useSWR(
    ["news", ticker],
    () => newsApi.get(ticker),
    { refreshInterval: 300_000, dedupingInterval: 60_000 },
  );

  if (isLoading) {
    return (
      <div>
        {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (error) {
    const is503 = error?.status === 503;
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
          {is503 ? "FMP API 키 미설정" : "뉴스를 불러올 수 없습니다"}
        </span>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
          {ticker} 뉴스 없음
        </span>
      </div>
    );
  }

  return (
    <div>
      {data.items.map((item) => (
        <NewsCard key={item.url} item={item} />
      ))}
    </div>
  );
}
