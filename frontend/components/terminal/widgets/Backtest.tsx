"use client";
import Link from "next/link";

export function BacktestWidget() {
  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="text-[var(--color-text-secondary)]">백테스트 결과를 보려면 전체 페이지를 이용하세요.</p>
      <Link href="/backtest" className="text-[var(--color-primary)] hover:underline" target="_blank">
        백테스트 페이지 열기 →
      </Link>
    </div>
  );
}
