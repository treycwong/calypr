import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

import { AnalyticsInit } from "@/components/analytics-init";
import { ToastProvider } from "@/components/ui/toast";

// Display / headings — PP Hatton (self-hosted, see src/fonts).
const hatton = localFont({
  variable: "--font-hatton",
  display: "swap",
  src: [
    { path: "../fonts/PPHatton-Medium.woff2", weight: "500", style: "normal" },
    { path: "../fonts/PPHatton-Medium.woff", weight: "500", style: "normal" },
    { path: "../fonts/PPHatton-Bold.woff2", weight: "700", style: "normal" },
    { path: "../fonts/PPHatton-Bold.woff", weight: "700", style: "normal" },
    { path: "../fonts/PPHatton-Ultrabold.woff2", weight: "800", style: "normal" },
    { path: "../fonts/PPHatton-Ultrabold.woff", weight: "800", style: "normal" },
  ],
});

// Body — PP Mori (self-hosted).
const mori = localFont({
  variable: "--font-mori",
  display: "swap",
  src: [
    { path: "../fonts/PPMori-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/PPMori-Regular.woff", weight: "400", style: "normal" },
    { path: "../fonts/PPMori-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "../fonts/PPMori-SemiBold.woff", weight: "600", style: "normal" },
    { path: "../fonts/PPMori-ExtraBold.woff2", weight: "800", style: "normal" },
    { path: "../fonts/PPMori-ExtraBold.woff", weight: "800", style: "normal" },
  ],
});

// Retained for monospace UI chrome (labels, timestamps) and blog code blocks.
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
      className={`dark ${mori.variable} ${hatton.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AnalyticsInit />
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
