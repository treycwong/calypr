// The facts the Terms and Privacy pages state about who runs Calypr. One place, because each is
// quoted on both pages and a mismatch between them is worse than either being vague.
//
// DRAFT (2026-11-03): the bracketed values are blanks for the founder to fill in before these
// pages go live. They are business and legal decisions, not things the code can know. Have the
// finished pages read by someone qualified in your jurisdiction; these drafts describe what the
// product actually does, which is the half a lawyer can't get from a template.

export const LEGAL = {
  /** The legal person or company that operates Calypr and that customers contract with. */
  operator: "[Your legal name or company]",
  /** Where that operator is based, as it should appear in the Terms. */
  operatorLocation: "[Country]",
  /** The law that governs the Terms, and where disputes are heard. */
  governingLaw: "[Country / state]",
  /** The youngest a user may be. 16 covers the strictest common default (the EU's GDPR); paid
   *  plans may want 18. */
  minimumAge: 16,
  contactEmail: "support@calypr.co",
  /** Shown as "Last updated" on both pages. Change it whenever either page changes. */
  lastUpdated: "3 November 2026",
} as const;
