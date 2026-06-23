import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { clerkEnabled } from "@/lib/auth";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Calypr — design AI agents on a canvas, leave with the code",
  description:
    "A no-ceiling agent builder. Drag nodes onto a canvas, run them live, and export idiomatic LangGraph you own.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const tree = (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );

  // Clerk only wraps the app when configured; otherwise the dev-auth path renders plainly
  // (so local + CI run with no keys). Its widgets are themed to match the monochrome app.
  if (!clerkEnabled()) return tree;
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorBackground: "#0a0a0a",
          colorPrimary: "#fafafa",
          borderRadius: "0.625rem",
        },
      }}
    >
      {tree}
    </ClerkProvider>
  );
}
