// The plan matrix, in one place.
//
// This copy used to live in three files — /pricing, the checkout confirmation, and the Settings
// plan badge — and had already drifted once. Every limit here is enforced by
// `entitlements.LIMITS` in the API; if you change a number, change it there too, because this
// module is what the customer is promised and that one is what they get.
//
// Client-safe and dependency-free so any of the three can import it.

export const PLAN_LIMITS = {
  free: { projects: 3, workspaces: 1, credits: 100, storage: "500 MB" },
  plus: { projects: 20, workspaces: 3, credits: 2_000, storage: "5 GB" },
} as const;

export const FREE_FEATURES = [
  "1 workspace, 3 projects",
  "100 credits a month, across runs and the assistant",
  "500 MB of storage",
  "Every block, template and canvas run",
  "Keep going on your own key when the credits run out",
  "Share links, run-capped per link",
] as const;

export const PLUS_FEATURES = [
  "Everything in Free",
  "Code export — edit the generated Python and apply it back to the canvas",
  "3 workspaces, 20 projects pooled across them",
  "2,000 credits a month, shared across runs and the assistant",
  "5 GB of storage",
  "Platform keys on every model — nothing to set up",
  "Your own keys still run free, at zero credits",
  "Credits reset at the start of each month",
] as const;

/** The short form the checkout page confirms with. It restates a decision made a click ago
 * rather than re-selling it, so it is deliberately not the full list. */
export const CHECKOUT_INCLUDED = [
  "Code export — the generated Python, yours to edit and run",
  "3 workspaces, 20 projects pooled across them",
  "2,000 credits a month across runs and the assistant",
  "5 GB of storage",
  "Platform keys on every model",
] as const;

/** The plan badge + one-line summary in Settings → Billing. */
export const PLAN_COPY: Record<string, { label: string; blurb: string }> = {
  free: {
    label: "Free",
    blurb: "1 workspace and 3 projects. Code export is a Plus feature.",
  },
  beta: {
    label: "Beta",
    blurb:
      "Early access, including code export — editing the generated Python and applying it back to the canvas.",
  },
  plus: {
    label: "Plus",
    blurb:
      "3 workspaces, 20 projects pooled across them, and code export — the generated Python is yours to edit, download and run anywhere.",
  },
};
