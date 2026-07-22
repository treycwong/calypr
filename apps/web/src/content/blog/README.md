# How to write a blog post

Posts live in this folder as `.mdx` files. There is no CMS — **git is the CMS**: add a file,
merge to `main`, and Vercel deploys it. Live at [calypr.co/blog](https://www.calypr.co/blog).

## Step by step

### 1. Create the file

Add a new file in this folder. The **filename becomes the URL slug**:

```
apps/web/src/content/blog/my-post-title.mdx  →  calypr.co/blog/my-post-title
```

Use short, lowercase, hyphenated names (they're permanent once shared — changing the
filename changes the URL).

### 2. Add the metadata block (required)

Every post must start with an exported `metadata` object. The build **fails** if `title`,
`date`, or `category` is missing — that's intentional, so a half-filled post can't ship.

```js
export const metadata = {
  title: "My post title",
  description: "One or two sentences. Shown on the index, in search results, and social cards.",
  date: "2026-07-16",              // ISO date; index sorts newest-first by this
  category: "tutorial",            // "tutorial" or "update" — drives the filter chips
  tags: ["canvas", "codegen"],     // optional; emitted as article:tag OG meta
  draft: true,                     // optional; true = hidden from index, sitemap, and build
};
```

### 3. Write the body

Everything after the metadata block is GitHub-flavored markdown (MDX):

- `## Heading` / `### Subheading` — start at `##` (the page renders `title` as the `<h1>`)
- **bold**, *italic*, `inline code`, [links](https://example.com), images, blockquotes
- Tables work (GFM)
- Code blocks get shiki syntax highlighting; add a filename title with:

  ````md
  ```python title="agent.py"
  def build_graph():
      ...
  ```
  ````

- Relative links like `[open the canvas](/canvas)` work and stay environment-correct.

### 4. Preview locally

```bash
pnpm dev          # from the repo root → http://localhost:3000/blog
```

The dev server picks up new/edited `.mdx` files on refresh. Check: the index lists your
post, the filter chip matches its category, and code blocks/tables render.

### 5. Ship it

```bash
git checkout -b post/my-post-title
git add apps/web/src/content/blog/my-post-title.mdx
git commit -m "post: my post title"
git push -u origin post/my-post-title
gh pr create        # merge when CI is green
```

Merging to `main` auto-deploys. **No other files need touching** — the index, the
`/blog/[slug]` page, the sitemap, and the OG/social tags are all generated from this
folder at build time.

### 6. Verify in prod (optional, ~1 min after merge)

```bash
curl -s https://www.calypr.co/sitemap.xml | grep my-post-title
curl -s https://www.calypr.co/blog/my-post-title | grep 'og:title'
```

## Quick reference

| Want to… | Do |
| --- | --- |
| Save an unfinished draft | `draft: true` in metadata (safe to merge — it won't render anywhere) |
| Publish a draft | Remove `draft: true`, merge |
| Edit a live post | Edit the `.mdx`, merge (URL/date unchanged) |
| Unpublish | Delete the file (or set `draft: true`), merge |
| New category | Categories are fixed to `tutorial`/`update` — adding one means updating `PostCategory` in `src/lib/blog.ts` and the chips in `src/app/blog/PostList.tsx` |

## Gotchas (MDX ≠ plain markdown)

- `{`, `}`, and `<` in **prose** are parsed as JSX — escape them (`\{`) or put them in
  backticks. Inside code blocks/fences they're fine.
- The `title="…"` on a code fence is the only fence attribute wired up; language tags
  (`python`, `ts`, `bash`, `text`…) control highlighting.
- Don't name a post the same as an existing one — slugs must be unique (filenames enforce
  this naturally).
