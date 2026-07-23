/**
 * The wordmark, as one component — `/logo.svg`, the same file the homepage hero nav uses.
 *
 * Before this, `SiteHeader` and `SiteFooter` rendered a *different* mark (`Wordmark`: a small
 * diamond glyph + "Calypr" in the heading font) while the landing page used this logotype. Same
 * brand, two different logos depending which page you were on. The SVG's paths are already
 * `fill="white"`, and the root layout forces dark mode unconditionally (`<html className="dark
 * …">`), so no colour handling is needed here — unlike `LandingHeader`, which keeps its own
 * `invert` filter because it sits over photographic hero art rather than the flat background
 * every other page has.
 */
export function SiteLogo({ className = "h-6 w-auto" }: { className?: string }) {
  // eslint-disable-next-line @next/next/no-img-element -- a static asset, not an optimizable photo
  return <img src="/logo.svg" alt="Calypr" width={87} height={25} className={className} />;
}
