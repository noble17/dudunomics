"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/portfolio", label: "포트폴리오" },
  { href: "/watchlist", label: "관심종목" },
  { href: "/holdings", label: "보유종목" },
  { href: "/backtest", label: "백테스트" },
  { href: "/stocks", label: "종목검색" },
  { href: "/screener", label: "종목분석" },
  { href: "/growth", label: "좋은종목찾기" },
  { href: "/terminal", label: "터미널" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-screen-xl items-center gap-6 px-6">
        <Link
          href="/portfolio"
          className="font-heading text-base font-bold tracking-tight text-foreground"
        >
          Dudunomics
        </Link>
        <div className="flex h-14">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center px-3 text-sm font-medium transition-colors ${
                pathname.startsWith(href)
                  ? "border-b-2 border-primary text-primary"
                  : "border-b-2 border-transparent text-muted-foreground hover:border-primary/40 hover:text-foreground"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
