// The facts the Terms and Privacy pages state about who runs Calypr. One place, because each is
// quoted on both pages and a mismatch between them is worse than either being vague.
//
// Filled in by the founder on 2026-11-03. These are business and legal decisions, not things the
// code can know; an E2E guard (landing.spec) fails if any value here is a [bracketed] blank. The
// pages describe what the product actually does — have them read by someone qualified in
// Malaysia before relying on them.

export const LEGAL = {
  /** Who operates Calypr and whom customers contract with. Calypr Co. is a trading name, not a
   *  separate company, so the person behind it is named. */
  operator: "Tracey Wong, trading as Calypr Co.",
  /** Where that operator is based, as it should appear in the Terms. */
  operatorLocation: "Malaysia",
  /** The law that governs the Terms, and where disputes are heard. */
  governingLaw: "Malaysia",
  /** The youngest a user may be. 16 covers the strictest common default (the EU's GDPR); paid
   *  plans may want 18. */
  minimumAge: 16,
  contactEmail: "support@calypr.co",
  /** Shown as "Last updated" on both pages. Change it whenever either page changes. */
  lastUpdated: "3 November 2026",
} as const;
