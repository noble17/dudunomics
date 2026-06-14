import type { Metadata } from "next";
import { Roboto, Roboto_Mono, Noto_Sans_KR } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { ThemeScript } from "@/components/theme-script";

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
    <html lang="ko" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body
        className={`${roboto.variable} ${robotoMono.variable} ${notoSansKR.variable} min-h-screen overflow-x-auto bg-background antialiased`}
      >
        <Nav />
        <main className="mx-auto w-full min-w-[1180px] px-4 py-6 2xl:px-5">{children}</main>
      </body>
    </html>
  );
}
