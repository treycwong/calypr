import fs from "node:fs";
import path from "node:path";

// Blog content pipeline: posts are .mdx files in src/content/blog, each exporting a
// `metadata` object (the @next/mdx-native alternative to YAML frontmatter — no extra deps).
// Slugs are filenames; the [slug] route dynamic-imports the same files for rendering.

export type PostCategory = "tutorial" | "update";

export type PostMeta = {
  slug: string;
  title: string;
  description: string;
  /** ISO date, e.g. "2026-07-15" */
  date: string;
  category: PostCategory;
  tags?: string[];
  draft?: boolean;
};

const CONTENT_DIR = path.join(process.cwd(), "src/content/blog");

export function postSlugs(): string[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs
    .readdirSync(CONTENT_DIR)
    .filter((f) => f.endsWith(".mdx"))
    .map((f) => f.replace(/\.mdx$/, ""));
}

/** All published posts, newest first. Throws at build time if a post omits required fields. */
export async function getPosts(): Promise<PostMeta[]> {
  const posts = await Promise.all(
    postSlugs().map(async (slug) => {
      const mod = await import(`@/content/blog/${slug}.mdx`);
      const meta = mod.metadata as Omit<PostMeta, "slug"> | undefined;
      if (!meta?.title || !meta.date || !meta.category) {
        throw new Error(`blog post "${slug}" must export metadata {title, date, category}`);
      }
      return { slug, ...meta };
    }),
  );
  return posts
    .filter((p) => !p.draft)
    .sort((a, b) => b.date.localeCompare(a.date));
}
