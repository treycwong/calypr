import type { MDXComponents } from "mdx/types";

// Required by @next/mdx with the App Router (see the vendored MDX guide). Element styling
// lives in the `.prose-blog` CSS block (globals.css) so markdown output stays plain HTML;
// this file only overrides what CSS can't express.
const components: MDXComponents = {};

export function useMDXComponents(): MDXComponents {
  return components;
}
