"use client";
import dynamic from "next/dynamic";
import { GlobalNav } from "@/components/terminal/GlobalNav";
import { IndexStrip } from "@/components/terminal/IndexStrip";
import { CommandPalette } from "@/components/terminal/CommandPalette";

const TabShell = dynamic(
  () => import("@/components/terminal/TabShell").then(m => m.TabShell),
  { ssr: false, loading: () => (
    <div className="flex-1 flex items-center justify-center text-xs font-data text-[var(--color-text-secondary)]">
      터미널 로딩 중…
    </div>
  )}
);

export default function TerminalPage() {
  return (
    <div className="terminal-dark fixed inset-0 z-50 flex flex-col bg-[var(--color-bg-primary)] overflow-hidden">
      <GlobalNav />
      <IndexStrip />
      <TabShell />
      <CommandPalette />
    </div>
  );
}
