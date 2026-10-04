import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/Footer";
import { SITE_HEADER_CTA } from "@/components/site/nav";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { postSlugs, type PostMeta } from "@/lib/blog";

// Posts are statically generated from src/content/blog at build time; unknown slugs 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return postSlugs().map((slug) => ({ slug }));
}

type Props = { params: Promise<{ slug: string }> };

async function loadPost(slug: string) {
  const mod = await import(`@/content/blog/${slug}.mdx`);
  return {
    Post: mod.default as React.ComponentType,
    meta: mod.metadata as Omit<PostMeta, "slug">,
  };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { meta } = await loadPost(slug);
  return {
    title: `${meta.title} — Calypr`,
    description: meta.description,
    alternates: { canonical: `/blog/${slug}` },
    openGraph: {
      title: meta.title,
      description: meta.description,
      type: "article",
      url: `/blog/${slug}`,
      publishedTime: `${meta.date}T00:00:00.000Z`,
      tags: meta.tags,
    },
    twitter: {
      card: "summary_large_image",
      title: meta.title,
      description: meta.description,
    },
  };
}

export default async function BlogPost({ params }: Props) {
  const { slug } = await params;
  const { Post, meta } = await loadPost(slug);

  return (
    // `prose-blog` follows the app's surface tokens for free, since every rule in it is written against
    // `--foreground` / `--muted-foreground` / `--card` / `--border` rather than literals.
    <div
      className="relative isolate flex min-h-screen flex-col bg-background"
    >
      {/* No `GridLines` here, unlike the index and /pricing: this is the one long-form reading
          surface on the site, and a repeating vertical rule field behind 2,000 words of prose
          and a code block is texture competing with the text. */}
      <LandingHeader cta={SITE_HEADER_CTA} sticky />

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-20">
        <Link
          href="/blog"
          className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)] transition-colors duration-200 hover:text-[var(--accent-on-dark)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.75} />
          Blog
        </Link>
        <header className="mt-8">
          <div className="flex items-center gap-3 font-mono text-[11px] font-bold uppercase tracking-[0.14em]">
            <span className="rounded-[6px] bg-[var(--eyebrow-bg)] px-[7px] py-[3px] text-[var(--accent-on-dark)]">
              {meta.category === "tutorial" ? "tutorial" : "product update"}
            </span>
            <span aria-hidden className="h-px w-9 bg-[var(--border-dark-strong)]" />
            <time dateTime={meta.date} className="font-medium text-[var(--text-on-dark-muted)]">
              {meta.date}
            </time>
          </div>
          {/* Display register: light weight, negative tracking, size doing the work — the same
              setting as every heading on the marketing surface. A post title set at
              `font-semibold` was the loudest type on the site. */}
          <h1 className="mt-5 text-balance font-heading text-[clamp(2rem,4.5vw,2.75rem)] font-light leading-[1.12] tracking-[-0.02em] text-[var(--text-on-dark)]">
            {meta.title}
          </h1>
          <p className="mt-4 max-w-[62ch] text-pretty text-[17px] leading-[1.55] text-[var(--text-on-dark-muted)]">
            {meta.description}
          </p>
        </header>

        <hr className="mt-10 border-[var(--border-dark)]" />

        <article className="prose-blog mt-8">
          <Post />
        </article>
      </main>

      <SiteFooter />
    </div>
  );
}
