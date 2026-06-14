"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme-toggle";

const links = [
  { href: "/portfolio", label: "포트폴리오", match: ["/portfolio", "/holdings"] },
  { href: "/watchlist", label: "관심종목", match: ["/watchlist"] },
  { href: "/candidates", label: "후보발굴", match: ["/candidates"] },
  { href: "/stocks", label: "종목분석", match: ["/stocks", "/screener", "/growth"] },
  { href: "/backtest", label: "전략", match: ["/backtest"] },
  { href: "/manage", label: "관리", match: ["/manage", "/data-sources", "/jobs"] },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background">
      <div className="mx-auto flex h-14 w-full min-w-[1180px] items-center gap-4 px-4 2xl:px-5">
        <Link
          href="/portfolio"
          className="shrink-0 font-heading text-base font-bold tracking-tight text-foreground"
        >
          Dudunomics
        </Link>
        <div className="flex h-14 min-w-0 flex-1 overflow-x-auto">
          {links.map(({ href, label, match }) => {
            const active = match.some((path) => pathname.startsWith(path));
            return (
            <Link
              key={href}
              href={href}
              className={`flex shrink-0 items-center whitespace-nowrap px-3 text-sm font-medium transition-colors ${
                active
                  ? "border-b-2 border-primary text-primary"
                  : "border-b-2 border-transparent text-muted-foreground hover:border-primary/40 hover:text-foreground"
              }`}
            >
              {label}
            </Link>
            );
          })}
        </div>
        <ThemeToggle />
      </div>
    </nav>
  );
}
