/**
 * The site's navigation, in one place.
 *
 * There used to be two headers — `LandingHeader` floating over the hero media and a `SiteHeader`
 * on every other route — and they had drifted into offering different *links* ("How it works"
 * vs "Features", "Open canvas" vs the waitlist), then into looking like two different sites.
 * There is one now: `LandingHeader`, sticky on the inner pages, with this one link list and
 * this one call to action.
 *
 * The homepage used to offer "Join Beta" here, onto an invite-only waitlist. Calypr has been
 * open and selling since the 2026-11-02 retier, so that sent first-time visitors to a queue for
 * something they could already use; every page now offers the same "Get Started".
 */
export const SITE_NAV = [
  { label: "Features", href: "/#features" },
  { label: "Templates", href: "/#templates" },
  { label: "Blog", href: "/blog" },
  { label: "Pricing", href: "/pricing" },
] as const;

/**
 * The header's call to action, on every page. Goes to **sign-up**, not sign-in: the person
 * clicking "Get Started" is by definition new, and /sign-in greets them with "Welcome back".
 * Social sign-in creates the account from either page, so this is copy, not a different flow.
 */
export const SITE_HEADER_CTA = { label: "Get Started", href: "/sign-up" } as const;
