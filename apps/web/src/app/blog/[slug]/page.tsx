import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
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
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-16">
        <Link
          href="/blog"
          className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          ← blog
        </Link>
        <header className="mt-6">
          <div className="flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            <span>{meta.category === "tutorial" ? "tutorial" : "product update"}</span>
            <span aria-hidden>·</span>
            <time dateTime={meta.date}>{meta.date}</time>
          </div>
          <h1 className="mt-4 text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            {meta.title}
          </h1>
          <p className="mt-3 text-pretty text-base leading-relaxed text-muted-foreground">
            {meta.description}
          </p>
        </header>

        <article className="prose-blog mt-10">
          <Post />
        </article>
      </main>

      <SiteFooter />
    </div>
  );
}
