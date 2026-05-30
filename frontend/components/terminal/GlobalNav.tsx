"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useCommandStore } from "@/lib/stores/command";
import { UserMenu } from "@/components/user-menu";
import useSWR from "swr";

type TabKey = "markets" | "portfolio" | "research" | "tools" | "ai";

const TABS: { key: TabKey; label: string }[] = [
  { key: "markets",   label: "MARKETS" },
  { key: "portfolio", label: "PORTFOLIO" },
  { key: "research",  label: "RESEARCH" },
  { key: "tools",     label: "TOOLS" },
  { key: "ai",        label: "AI" },
];

function useMe() {
  return useSWR("/api/auth/me", () =>
    fetch("/api/auth/me", { credentials: "include" }).then(r => r.ok ? r.json() : null)
  );
}

function GlobalNavInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const openPalette = useCommandStore(s => s.openPalette);
  const { data: me } = useMe();
  const activeTab = searchParams.get("tab") ?? "markets";

  function switchTab(key: TabKey) {
    router.push(`/terminal?tab=${key}`);
  }

  return (
    <div className="flex items-center justify-between px-4 h-10 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      <div className="flex items-center h-full">
        <span className="font-data text-sm font-bold text-[var(--color-primary)] mr-6 shrink-0">
          Dudunomics
        </span>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => switchTab(tab.key)}
            className={[
              "h-full px-4 text-[13px] font-data tracking-wider transition-colors shrink-0",
              activeTab === tab.key
                ? "border-t-2 border-[var(--color-primary)] bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={openPalette}
          className="flex items-center gap-2 text-[13px] font-data text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded px-3 py-1 hover:border-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <span>LLM &lt;GO&gt;</span>
          <kbd className="text-[12px] bg-[var(--color-bg-primary)] px-1 rounded">⌘K</kbd>
        </button>
        <button
          disabled
          className="text-[13px] font-data text-[var(--color-text-muted)] border border-[var(--color-border)] rounded px-3 py-1 cursor-not-allowed opacity-40"
        >
          AI COPILOT
        </button>
        {me?.email && <UserMenu email={me.email} />}
      </div>
    </div>
  );
}

export function GlobalNav() {
  return (
    <Suspense fallback={
      <div className="h-10 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)] shrink-0" />
    }>
      <GlobalNavInner />
    </Suspense>
  );
}
