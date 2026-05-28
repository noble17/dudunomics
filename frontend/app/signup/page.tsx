"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "회원가입 실패");
        return;
      }
      router.push("/portfolio");
      router.refresh();
    } catch {
      setError("서버 연결 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)]">
      <div className="w-full max-w-sm p-8 border border-[var(--color-border)] rounded-[var(--radius-lg)] bg-[var(--color-bg-secondary)]">
        <h1 className="text-xl font-semibold mb-6 text-[var(--color-text-primary)]">회원가입</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">이메일</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              required autoFocus
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-text-secondary)] mb-1">비밀번호 (6자 이상)</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              required minLength={6}
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg-primary)] border border-[var(--color-border)] rounded text-[var(--color-text-primary)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          {error && <p className="text-xs text-[var(--color-fall)]">{error}</p>}
          <button
            type="submit" disabled={loading}
            className="w-full py-2 text-sm font-medium bg-[var(--color-primary)] text-white rounded hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "처리 중…" : "회원가입"}
          </button>
        </form>
        <p className="mt-4 text-xs text-center text-[var(--color-text-secondary)]">
          이미 계정이 있으신가요?{" "}
          <a href="/login" className="text-[var(--color-primary)] hover:underline">로그인</a>
        </p>
      </div>
    </div>
  );
}
