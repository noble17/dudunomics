"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { alertsApi } from "@/lib/api";
import type { AlertCondition, AlertEvent, AlertIn } from "@/lib/types";

interface Toast {
  id: number
  message: string
}

let _toastId = 0;

export function useAlerts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seenIds = useRef<Set<number>>(new Set());

  const { data: conditions = [], mutate: mutateConditions } =
    useSWR<AlertCondition[]>("/api/alerts", alertsApi.list, { refreshInterval: 30_000 });

  const { data: unread = [], mutate: mutateUnread } =
    useSWR<AlertEvent[]>("/api/alerts/events/unread", alertsApi.unread, { refreshInterval: 10_000 });

  // 새 미읽음 이벤트 → 토스트
  useEffect(() => {
    const newEvents = unread.filter((e) => !seenIds.current.has(e.id));
    if (!newEvents.length) return;

    for (const ev of newEvents) {
      seenIds.current.add(ev.id);
      const msg = formatConditionMsg(ev);
      const id = ++_toastId;
      setToasts((prev) => [...prev, { id, message: msg }]);
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
    }

    alertsApi.markRead().then((res) => {
      if (res && !res.ok) {
        for (const ev of newEvents) seenIds.current.delete(ev.id);
      }
      mutateUnread();
    }).catch(() => {
      for (const ev of newEvents) seenIds.current.delete(ev.id);
    });
  }, [unread, mutateUnread]);

  async function addAlert(body: AlertIn) {
    await alertsApi.create(body);
    mutateConditions();
  }

  async function removeAlert(id: number) {
    await alertsApi.delete(id);
    mutateConditions();
  }

  return { conditions, unread, toasts, addAlert, removeAlert };
}

export function formatConditionMsg(ev: AlertEvent): string {
  const price = ev.triggered_price.toFixed(2);
  switch (ev.condition_type) {
    case "price_above": return `${ev.ticker} $${price} ▲ ${ev.condition_value} 돌파`;
    case "price_below": return `${ev.ticker} $${price} ▼ ${ev.condition_value} 하향`;
    case "rsi_above":   return `${ev.ticker} RSI 과매수(>${ev.condition_value}) @ $${price}`;
    case "rsi_below":   return `${ev.ticker} RSI 과매도(<${ev.condition_value}) @ $${price}`;
    case "ma_golden_cross": return `${ev.ticker} MA 골든크로스 발생`;
    case "ma_dead_cross":   return `${ev.ticker} MA 데드크로스 발생`;
    default: return `${ev.ticker} 알림 발생`;
  }
}
