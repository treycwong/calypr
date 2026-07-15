import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Let .mdx files participate in routing/imports (blog posts live in src/content/blog).
  pageExtensions: ["ts", "tsx", "md", "mdx"],
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
