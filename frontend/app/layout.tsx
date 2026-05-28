import type { Metadata } from "next";
import { Roboto, Roboto_Mono, Noto_Sans_KR } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-roboto",
  display: "swap",
});

const robotoMono = Roboto_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-roboto-mono",
  display: "swap",
});

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-noto-sans-kr",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Dudunomics",
  description: "글로벌 포트폴리오 + 퀀트 분석",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body
        className={`${roboto.variable} ${robotoMono.variable} ${notoSansKR.variable} min-h-screen bg-background antialiased`}
      >
        <Nav />
        <main className="mx-auto max-w-screen-xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
