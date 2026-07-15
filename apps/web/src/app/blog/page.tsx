import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
import { getPosts } from "@/lib/blog";

import { PostList } from "./PostList";

export const metadata: Metadata = {
  title: "Blog — Calypr",
  description: "Tutorials and product updates from Calypr — the no-ceiling agent builder.",
};

export default async function BlogIndex() {
  const posts = await getPosts();

  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-5 py-16">
        <span className="inline-flex items-center rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          blog
        </span>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
          Tutorials &amp; product updates
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Build guides for the canvas, and what shipped — straight from the repo.
        </p>

        <div className="mt-10">
          <PostList posts={posts} />
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
