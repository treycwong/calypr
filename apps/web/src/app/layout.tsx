import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { AnalyticsInit } from "@/components/analytics-init";
import { ToastProvider } from "@/components/ui/toast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Lets route metadata (blog posts, OG urls) use relative paths that resolve to prod.
  metadataBase: new URL("https://www.calypr.co"),
  title: "Calypr — design AI agents on a canvas, leave with the code",
  description:
    "A no-ceiling agent builder. Drag nodes onto a canvas, run them live, and export idiomatic LangGraph you own.",
  openGraph: {
    siteName: "Calypr",
    type: "website",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Better Auth needs no provider wrapper; the auth client talks to /api/auth directly.
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AnalyticsInit />
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
