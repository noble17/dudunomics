import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  return (
    <button
      type="button"
      data-theme-toggle
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-border bg-card text-muted-foreground transition-colors hover:border-primary hover:text-primary"
      title="테마 전환"
      aria-label="테마 전환"
    >
      <Sun className="theme-icon-sun h-4 w-4" />
      <Moon className="theme-icon-moon h-4 w-4" />
    </button>
  );
}
