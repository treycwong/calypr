# Calypr — Blog (tutorials + product updates): MDX-in-repo, no CMS (execution plan)

**Date:** 2026-07-15 · **Status:** PLAN · Marketing/top-of-funnel surface (SEO, activation
tutorials, credibility). Feeds the Week-11 OSS launch (Show HN needs content to land on), but per
`ROADMAP-6M.md`'s anti-scope-expansion rules it must not eat engineering weeks or add operational
surface. ~2 days, two PRs, web-only.

## 0. The decision: repo-MDX beats both a CMS and "build it in our app"

**Recommendation: MDX files in the repo, rendered by the existing Next.js app. Git is the CMS.**

- **Headless CMS (Sanity/Contentful/Payload/Strapi): no.** Accounts, schemas, API tokens,
  webhooks, preview envs, a second content database — real operational surface for a solo founder
  who writes in markdown anyway. Zero benefit until there are non-technical authors. Revisit then.
- **DB-backed posts + admin UI in the product: no.** That's building a CMS product inside a
  startup whose roadmap explicitly forbids scope expansion. The agent canvas is not a content
  platform.
- **MDX-in-repo: yes.** Zero new infra; posts are version-controlled and PR-reviewable; deploys
  ride the existing push-to-main Vercel pipeline; the writing workflow is the editor the founder
  already lives in (and Claude can draft posts as PRs). The standard dev-tool-startup pattern
  (Vercel/Linear/Resend-style).

**Naming:** call the section **Blog** (or Guides). "Knowledge Base" collides with the product's
RAG Knowledge Base feature (`RAG-INGESTION-PLAN.md`) and would confuse users.

## 1. Verified current state (code audit 2026-07-15)

- Next.js **16.2.9**, App Router, Tailwind **v4** (CSS-first `@theme` in
  `apps/web/src/app/globals.css`), shadcn primitives in `components/ui/`, Geist Sans/Mono,
  **dark-locked monochrome** design language.
- `apps/web/next.config.ts` is empty; **no markdown/MDX deps anywhere** in the monorepo.
- `components/Markdown.tsx` (used by ShareChat/Playground) is a tiny regex renderer — **no
  links, images, code blocks, or tables** — inadequate for tutorials. Don't extend it; leave it
  to the chat surfaces.
- Landing header/footer live **inline in `src/app/page.tsx`** (~420 lines) — must be extracted
  for the blog to share chrome.
- **SEO scaffolding absent**: no `sitemap.ts`, `robots.ts`, per-route `generateMetadata`, or OG
  images. The blog is the natural forcing function to add all of it (benefits the whole site).

## 2. PR-1 — shared chrome + content pipeline + blog routes (~1.5d)

1. **Extract shared chrome:** pull the landing `<header>`/`<footer>` out of `page.tsx` into
   `components/site/Header.tsx` / `Footer.tsx`; landing re-imports them (pixel-unchanged).
2. **Content pipeline:** `apps/web/content/blog/*.mdx` with frontmatter (`title`, `description`,
   `date`, `category: "tutorial" | "update"`, `tags`, optional `draft`). RSC MDX rendering with:
   - frontmatter parsing (`gray-matter` or the pipeline's native support),
   - **code-block highlighting** (shiki-based, e.g. `rehype-pretty-code`) — tutorials are
     code-heavy, non-negotiable,
   - GitHub-flavored markdown (tables, links, images).
   - **Library choice made at implementation time from current docs** (`@next/mdx` vs
     `next-mdx-remote` RSC vs Velite): these APIs move fast and Next-16 compat must be verified
     against official docs, not memory. Criteria: RSC-native, no client JS for post bodies,
     minimal dep count (repo ethos — this codebase hand-wrote a markdown renderer to avoid deps).
3. **Routes:**
   - `src/app/blog/page.tsx` — index, newest-first, filter chips for Tutorials / Product updates.
   - `src/app/blog/[slug]/page.tsx` — post page via `generateStaticParams` (SSG; content is
     in-repo so posts are static at build).
   - Typography: a `prose`-style wrapper on the existing monochrome tokens (hand-rolled prose
     classes, or `@tailwindcss/typography` if it fits the token set).
4. **Nav:** add "Blog" to the extracted header.
5. **Seed content (2 real posts, one per category):** a tutorial (e.g. "Build a RAG agent on the
   canvas → own the Python") and a product update (the Week 1–5 changelog — already written in
   the shipped-week notes).

**Gates:** `pnpm --filter @calypr/web typecheck` + `lint` + production `next build`; browser-pane
check — index filters work, a post renders headings/links/images/tables + highlighted code,
landing pixel-unchanged after chrome extraction.

## 3. PR-2 — SEO scaffolding (site-wide win, ~0.5d)

- `src/app/sitemap.ts` (landing + all posts) and `src/app/robots.ts`.
- Per-post `generateMetadata` (title/description/OG/Twitter card, `article` type + dates).
- Optional if cheap: a static `opengraph-image` template for posts (skip dynamic OG generation
  while the Vercel preview-build issue is open).

**Gates:** `/sitemap.xml` + `/robots.txt` serve locally and in prod; a post's OG tags present
(`curl -s <post> | grep 'og:'`).

## 4. Explicitly NOT now

- No headless CMS, no admin UI, no DB tables for content, no comments, no RSS-driven email.
- No separate docs framework (Fumadocs et al.) — revisit only if the knowledge base outgrows a
  blog (e.g. at the Week-11 OSS docs push).

## 5. Files

- **New:** `apps/web/content/blog/*.mdx` · `src/app/blog/{page.tsx,[slug]/page.tsx}` ·
  `src/components/site/{Header,Footer}.tsx` · `src/app/{sitemap.ts,robots.ts}` · prose styles in
  `globals.css`.
- **Modified:** `src/app/page.tsx` (use extracted chrome) · `next.config.ts` (if the chosen MDX
  lib needs it) · `apps/web/package.json`.

## 6. Rollout

1. **PR-1** → CI green → merge → prod-verify `www.calypr.co/blog` renders both seed posts.
2. **PR-2** → CI green → merge → prod-verify sitemap/robots/OG.

Ships via Vercel production builds (the known preview-build failure doesn't block, per the
Week 2–5 cadence).
