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

const APP_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://dango-border.example.com";

export const metadata: Metadata = {
  metadataBase: new URL(APP_URL),
  title: {
    default: "だんごボーダー — IRIAMボーダー予測",
    template: "%s | だんごボーダー",
  },
  description:
    "IRIAMのランクボーダーをリアルタイム予測・監視。下振れ・目安・上振れ予測をAIがサポートします。",
  keywords: ["IRIAM", "ボーダー予測", "ランク", "だんごボーダー", "リアルタイム"],
  authors: [{ name: "だんごボーダー" }],
  openGraph: {
    type: "website",
    locale: "ja_JP",
    url: APP_URL,
    siteName: "だんごボーダー",
    title: "だんごボーダー — IRIAMボーダー予測",
    description:
      "IRIAMのランクボーダーをリアルタイム予測・監視。下振れ・目安・上振れ予測をAIがサポートします。",
    images: [
      {
        url: "/ogp.png",
        width: 1200,
        height: 630,
        alt: "だんごボーダー — IRIAMボーダー予測ダッシュボード",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "だんごボーダー — IRIAMボーダー予測",
    description:
      "IRIAMのランクボーダーをリアルタイム予測・監視。下振れ・目安・上振れ予測をAIがサポートします。",
    images: ["/ogp.png"],
  },
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
