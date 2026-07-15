"use client";

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
            className={`rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] transition-colors ${
              filter === value
                ? "border-foreground/40 bg-card text-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-8 divide-y divide-border border-y border-border">
        {visible.map((post) => (
          <Link
            key={post.slug}
            href={`/blog/${post.slug}`}
            className="group flex flex-col gap-2 py-7 transition-colors sm:flex-row sm:items-baseline sm:gap-8"
          >
            <div className="flex shrink-0 flex-col gap-1 sm:w-44">
              <time dateTime={post.date} className="font-mono text-xs text-muted-foreground">
                {post.date}
              </time>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                {CATEGORY_LABEL[post.category]}
              </span>
            </div>
            <div>
              <h2 className="text-lg font-medium tracking-tight transition-colors group-hover:text-foreground">
                {post.title}
              </h2>
              <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-muted-foreground">
                {post.description}
              </p>
            </div>
          </Link>
        ))}
        {visible.length === 0 && (
          <p className="py-10 text-sm text-muted-foreground">Nothing here yet.</p>
        )}
      </div>
    </div>
  );
}
