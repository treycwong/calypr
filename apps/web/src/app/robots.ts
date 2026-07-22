import type { MetadataRoute } from "next";

// Crawl the marketing surface (landing + blog); keep bots out of the app, the API, and
// share links — /s/{token} pages are unlisted by design (unguessable tokens), so letting
// them into an index would defeat the point. /checkout is a transactional step, not a page
// worth landing on from search (it also carries its own noindex).
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/checkout", "/dashboard", "/s/", "/sign-in"],
    },
    sitemap: "https://www.calypr.co/sitemap.xml",
  };
}
