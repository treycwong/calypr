/**
 * The site's navigation, in one place.
 *
 * There used to be two headers — `LandingHeader` floating over the hero media and a `SiteHeader`
 * on every other route — and they had drifted into offering different *links* ("How it works"
 * vs "Features", "Open canvas" vs the waitlist), then into looking like two different sites.
 * There is one now: `LandingHeader`, sticky on the inner pages. This module survives it because
 * the link list still wants one home, and because the CTA genuinely does differ per surface.
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
 * The inner pages' call to action — every page except the homepage, passed to `LandingHeader`
 * as `cta`. Goes straight to sign-in rather than the waitlist, matching the homepage's own hero
 * button: once billing is live, making a second visitor jump through the invite-only waitlist
 * just because they're on /pricing instead of / would be an inconsistency of its own.
 */
export const SITE_HEADER_CTA = { label: "Get Started", href: "/sign-in" } as const;
