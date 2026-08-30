import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Let .mdx files participate in routing/imports (blog posts live in src/content/blog).
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  images: {
    // Generated media lives in Vercel Blob, so the optimizer has to be told the host is ours
    // before `next/image` will touch it.
    //
    // This exists to stop the Media grid serving full-size originals as thumbnails. A
    // gpt-image-2 PNG is ~2.7 MB; the tile it renders into is ~180px. Browsing a page of sixty
    // pulled well over a hundred megabytes of blob transfer to draw postage stamps, which is the
    // kind of thing that quietly consumes a plan's monthly allowance.
    remotePatterns: [{ protocol: "https", hostname: "*.public.blob.vercel-storage.com" }],
  },
};

// Turbopack requires remark/rehype plugins by *string name* (options must be serializable —
// JS functions can't cross into Rust). See node_modules/next/dist/docs/01-app/02-guides/mdx.md.
const withMDX = createMDX({
  options: {
    remarkPlugins: ["remark-gfm"],
    rehypePlugins: [
      // shiki-based highlighting; `min-dark` is near-monochrome, matching the design language.
      // keepBackground off so `pre` uses our card token instead of the theme's background.
      ["rehype-pretty-code", { theme: "min-dark", keepBackground: false }],
    ],
  },
});

export default withMDX(nextConfig);
