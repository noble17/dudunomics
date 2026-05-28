"use client";
import dynamic from "next/dynamic";
import { GlobalNav } from "@/components/terminal/GlobalNav";
import { IndexStrip } from "@/components/terminal/IndexStrip";
import { CommandPalette } from "@/components/terminal/CommandPalette";

const Shell = dynamic(
  () => import("@/components/terminal/Shell").then(m => m.Shell),
  { ssr: false, loading: () => <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">터미널 로딩 중…</div> }
);

export default function TerminalPage() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--color-bg-primary)] overflow-hidden">
      <GlobalNav />
      <IndexStrip />
      <Shell />
      <CommandPalette />
    </div>
  );
}
