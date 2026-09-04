"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { PostCategory, PostMeta } from "@/lib/blog";

const FILTERS: { label: string; value: PostCategory | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Tutorials", value: "tutorial" },
  { label: "Product updates", value: "update" },
];

const CATEGORY_LABEL: Record<PostCategory, string> = {
  tutorial: "tutorial",
  update: "product update",
};

// Client-side category filter so the index stays fully static (no searchParams → no
// dynamic rendering); posts arrive as plain serializable metadata from the server page.
//
// Styled on Spectra: mono chips that go green when selected, hairline-separated rows, and a
// row that lights at the border and the arrow on hover without moving. Nothing here is a new
// device — the chips are the framework filters from the landing page's template carousel and
// the arrow is `FeatureCard`'s.
export function PostList({ posts }: { posts: PostMeta[] }) {
  const [filter, setFilter] = useState<PostCategory | "all">("all");
  const visible = filter === "all" ? posts : posts.filter((p) => p.category === filter);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map(({ label, value }) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
            className={`rounded-full border px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors duration-200 ${
              filter === value
                ? "border-[var(--border-accent)] bg-[var(--accent-soft-bg)] text-[var(--accent-on-dark)]"
                : "border-[var(--border-dark)] text-[var(--text-on-dark-faint)] hover:border-[var(--border-accent)] hover:text-[var(--text-on-dark)]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-10 border-t border-[var(--border-dark)]">
        {visible.map((post) => (
          <Link
            key={post.slug}
            href={`/blog/${post.slug}`}
            className="group flex flex-col gap-3 border-b border-[var(--border-dark)] py-8 transition-colors duration-200 hover:border-[var(--border-accent)] sm:flex-row sm:gap-10"
          >
            <div className="flex shrink-0 flex-col gap-1.5 sm:w-44 sm:pt-1">
              <time
                dateTime={post.date}
                className="font-mono text-xs text-[var(--text-on-dark-faint)]"
              >
                {post.date}
              </time>
              <span className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)] transition-colors duration-200 group-hover:text-[var(--accent-on-dark)]">
                {CATEGORY_LABEL[post.category]}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-medium tracking-[-0.02em] text-[var(--text-on-dark)]">
                {post.title}
              </h2>
              <p className="mt-2 max-w-[62ch] text-pretty text-[15px] leading-[1.55] text-[var(--text-on-dark-muted)]">
                {post.description}
              </p>
            </div>
            <ArrowRight
              className="hidden h-4 w-4 shrink-0 self-center text-[var(--accent-on-dark)] opacity-0 transition-opacity duration-200 group-hover:opacity-100 sm:block"
              strokeWidth={1.75}
            />
          </Link>
        ))}
        {visible.length === 0 && (
          <p className="border-b border-[var(--border-dark)] py-10 text-sm text-[var(--text-on-dark-muted)]">
            Nothing here yet.
          </p>
        )}
      </div>
    </div>
  );
}
