"use client";

import { useEffect, useRef, useState } from "react";
import { quotesApi } from "@/lib/api";
import type { QuotesOut } from "@/lib/types";

const POLL_INTERVAL_MS = 10_000;

export function useQuotes(): QuotesOut | null {
  const [quotes, setQuotes] = useState<QuotesOut | null>(null);
  const lastRef = useRef<QuotesOut | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      try {
        const data = await quotesApi.get();
        if (!cancelled) {
          lastRef.current = data;
          setQuotes(data);
        }
      } catch {
        // 오류 시 이전 값 유지 (깜빡임 방지)
        if (!cancelled && lastRef.current) {
          setQuotes(lastRef.current);
        }
      }
    }

    fetch();
    const id = setInterval(fetch, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return quotes;
}
