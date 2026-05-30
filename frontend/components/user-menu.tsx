"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props { email: string }

export function UserMenu({ email }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] px-2 py-1"
      >
        {email}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-32 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded z-[200]">
          <button
            onClick={logout}
            className="w-full text-left text-xs px-3 py-2 hover:bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]"
          >
            로그아웃
          </button>
        </div>
      )}
    </div>
  );
}
