import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Dudunomics",
  description: "글로벌 포트폴리오 + 퀀트 분석",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className={`${inter.className} min-h-screen bg-slate-50 antialiased`}>
        <Nav />
        <main className="mx-auto max-w-screen-xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
