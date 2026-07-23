/**
 * The site's navigation, in one place.
 *
 * There are two headers — `LandingHeader` floats over the hero media, `SiteHeader` is the
 * sticky one every other route uses — and they had drifted into offering different links and a
 * different call to action ("Join Waitlist" vs "Open canvas"). Same site, two answers to "where
 * can I go?", which is the sort of thing nobody notices until a visitor lands on /pricing from
 * search and finds a different product.
 *
 * The *styling* stays separate (one is white-on-media, one is not); only the content is shared,
 * so the two can look different without saying different things.
 */
export const SITE_NAV = [
  { label: "Features", href: "/#features" },
  { label: "Templates", href: "/#templates" },
  { label: "Blog", href: "/blog" },
  { label: "Tutorials", href: "/tutorials" },
  { label: "Pricing", href: "/pricing" },
] as const;

/**
 * The primary call to action.
 *
 * NOTE: this still points at the waitlist, which predates billing going live — anyone can now
 * buy Plus from /pricing without an invite. Worth revisiting as a product decision (see
 * TODO.md); kept here so it's one edit when that call is made, rather than two.
 */
export const SITE_CTA = { label: "Join Waitlist", href: "/waitlist" } as const;
