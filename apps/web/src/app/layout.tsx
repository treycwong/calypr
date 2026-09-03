import type { Metadata } from "next";
import { Figtree, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { AnalyticsInit } from "@/components/analytics-init";
import { HydrationMarker } from "@/components/hydration-marker";
import { ToastProvider } from "@/components/ui/toast";

/* Spectra is a one-sans system: a geometric-humanist grotesque for everything, plus one
   coding mono for labels. Figtree and JetBrains Mono are the bundle's own identified
   stand-ins (`tokens/fonts.css` says the source binaries were never supplied).

   The bundle loads both from the Google Fonts CSS API at runtime; `next/font/google`
   self-hosts them at build time instead, so there's no render-blocking third-party
   request and no layout shift.

   Weight 300 is not optional padding in this list — every display size and heading in
   Spectra is set light, and without it the browser synthesises the weight and the whole
   type register reads wrong. */
const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

// Mono labels only: `01 HARDWARE`, `MOST POPULAR`, `02 // SYSTEM ACTIVE`, and blog code.
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  // Lets route metadata (blog posts, OG urls) use relative paths that resolve to prod.
  metadataBase: new URL("https://www.calypr.co"),
  title: "Calypr | Build AI-Powered Workflows and Applications",
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
      className={`dark ${figtree.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AnalyticsInit />
        <HydrationMarker />
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
