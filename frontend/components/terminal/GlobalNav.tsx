"use client";
import Link from "next/link";
import { useCommandStore } from "@/lib/stores/command";
import { UserMenu } from "@/components/user-menu";
import useSWR from "swr";

function useMe() {
  return useSWR("/api/auth/me", () =>
    fetch("/api/auth/me", { credentials: "include" }).then(r => r.ok ? r.json() : null)
  );
}

export function GlobalNav() {
  const openPalette = useCommandStore(s => s.openPalette);
  const { data: me } = useMe();

  return (
    <div className="flex items-center justify-between px-4 h-10 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] shrink-0">
      <div className="flex items-center gap-4">
        <Link href="/portfolio" className="font-heading text-sm font-bold text-[var(--color-text-primary)]">
          Dudunomics
        </Link>
        <span className="text-[var(--color-border)]">|</span>
        <span className="text-xs text-[var(--color-text-secondary)]">Terminal</span>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={openPalette}
          className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded px-2 py-1 hover:border-[var(--color-primary)] hover:text-[var(--color-text-primary)] transition-colors"
        >
          <span>명령창</span>
          <kbd className="font-mono text-[10px] bg-[var(--color-bg-primary)] px-1 rounded">⌘K</kbd>
        </button>
        {me?.email && <UserMenu email={me.email} />}
      </div>
    </div>
  );
}
