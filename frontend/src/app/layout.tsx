import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "だんごボーダー — IRIAMボーダー予測",
  description: "IRIAMのランクボーダー予測・監視ダッシュボード。下振れ・目安・上振れ予測をサポート。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col text-foreground selection:bg-purple-500/30 selection:text-white transition-colors duration-300">
        <ThemeProvider>
          <div className="ambient-glow-1" aria-hidden="true" />
          <div className="ambient-glow-2" aria-hidden="true" />
          <div className="ambient-glow-3" aria-hidden="true" />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
