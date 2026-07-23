/**
 * The site's navigation, in one place.
 *
 * There are two headers — `LandingHeader` floats over the hero media, `SiteHeader` is the
 * sticky one every other route uses — and they had drifted into offering different *links*
 * ("How it works" vs "Features", "Open canvas" vs the waitlist). Same site, two answers to
 * "where can I go?", which is the sort of thing nobody notices until a visitor lands on
 * /pricing from search and finds a different product. The link list (`SITE_NAV`) is shared so
 * that can't happen again.
 *
 * The call to action is **deliberately not shared**: the homepage nav's "Join Beta" is the
 * still-invite-only path onto the free beta cohort, while every other page's "Get Started"
 * goes straight to sign-in — billing is live, so that's the honest primary action once someone
 * has scrolled past the hero. Two different buttons on purpose, not drift.
 */
export const SITE_NAV = [
  { label: "Features", href: "/#features" },
  { label: "Templates", href: "/#templates" },
  { label: "Blog", href: "/blog" },
  { label: "Tutorials", href: "/tutorials" },
  { label: "Pricing", href: "/pricing" },
] as const;

/**
 * `LandingHeader`'s call to action, on the homepage nav only.
 *
 * NOTE: this points at the waitlist, which predates billing going live — anyone can now buy
 * Plus from /pricing without an invite. Worth revisiting as a product decision (see TODO.md).
 */
export const SITE_CTA = { label: "Join Beta", href: "/waitlist" } as const;

/**
 * `SiteHeader`'s call to action — every page except the homepage. Goes straight to sign-in
 * rather than the waitlist, matching the homepage's own hero button: once billing is live,
 * making a second visitor jump through the invite-only waitlist just because they're on
 * /pricing instead of / would be an inconsistency of its own.
 */
export const SITE_HEADER_CTA = { label: "Get Started", href: "/sign-in" } as const;
