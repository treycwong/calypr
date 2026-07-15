import type { MetadataRoute } from "next";

// Crawl the marketing surface (landing + blog); keep bots out of the app, the API, and
// share links — /s/{token} pages are unlisted by design (unguessable tokens), so letting
// them into an index would defeat the point.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/dashboard", "/s/", "/sign-in"],
    },
    sitemap: "https://www.calypr.co/sitemap.xml",
  };
}
