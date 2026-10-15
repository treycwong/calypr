// The plan matrix, in one place.
//
// This copy used to live in three files — /pricing, the checkout confirmation, and the Settings
// plan badge — and had already drifted once. Every limit here is enforced by
// `entitlements.LIMITS` in the API; if you change a number, change it there too, because this
// module is what the customer is promised and that one is what they get.
//
// The 2026-10-14 retier (TODO.md §3a): Free / $5 Starter / $10 Plus. 3D and Video are on every
// plan, paid in credits; code export is Plus only.
//
// Client-safe and dependency-free so any page can import it.

export type PlanId = "free" | "starter" | "plus";

/** Plans a visitor can buy at /checkout. */
export const SELLABLE_PLANS = ["starter", "plus"] as const;
export type SellablePlan = (typeof SELLABLE_PLANS)[number];

export function isSellablePlan(plan: string | undefined): plan is SellablePlan {
  return (SELLABLE_PLANS as readonly string[]).includes(plan ?? "");
}

export const PLAN_LIMITS = {
  free: { projects: 3, workspaces: 1, credits: 100, storage: "500 MB" },
  starter: { projects: 10, workspaces: 1, credits: 500, storage: "2 GB" },
  plus: { projects: 20, workspaces: 3, credits: 1_000, storage: "5 GB" },
} as const;

/** The limits a plan is promised. `beta` is on Starter's allowance; an unknown plan reads as
 *  Free, the same fail-small rule as `entitlements.limits` on the API. */
export function planLimits(plan: string | undefined) {
  if (plan === "beta") return PLAN_LIMITS.starter;
  return PLAN_LIMITS[(plan as PlanId) in PLAN_LIMITS ? (plan as PlanId) : "free"];
}

export type PlanCard = {
  id: PlanId;
  name: string;
  /** Monthly price in USD. */
  price: number;
  pitch: string;
  features: readonly string[];
  /** The short list the checkout page confirms with. It restates a decision made a click ago
   *  rather than re-selling it, so it is deliberately not the full list. */
  included: readonly string[];
};

export const PLANS: Record<PlanId, PlanCard> = {
  free: {
    id: "free",
    name: "Free",
    price: 0,
    pitch: "Build and run real agents. No key, no card.",
    features: [
      "1 workspace, 3 projects",
      "100 credits a month, across runs and the assistant",
      "Every block, including Image, Voice, 3D and Video",
      "500 MB of storage",
      "Keep going on your own key when the credits run out",
      "Share links, run-capped per link",
    ],
    included: [],
  },
  starter: {
    id: "starter",
    name: "Starter",
    price: 5,
    pitch: "Five times the credits, for practising every day.",
    features: [
      "Everything in Free",
      "500 credits a month, across runs and the assistant",
      "1 workspace, 10 projects",
      "2 GB of storage",
      "Conversations remembered for 30 days, not 7",
      "Platform keys on every model, nothing to set up",
    ],
    included: [
      "500 credits a month across runs and the assistant",
      "1 workspace, 10 projects",
      "2 GB of storage",
      "Platform keys on every model",
    ],
  },
  plus: {
    id: "plus",
    name: "Plus",
    price: 10,
    pitch: "Twice the credits, room to organise, and the code to take with you.",
    features: [
      "Everything in Starter",
      "Code export: edit the generated Python and apply it back to the canvas",
      "1,000 credits a month, across runs and the assistant",
      "3 workspaces, 20 projects pooled across them",
      "5 GB of storage",
    ],
    included: [
      "Code export: the generated Python, yours to edit and run",
      "1,000 credits a month across runs and the assistant",
      "3 workspaces, 20 projects pooled across them",
      "5 GB of storage",
      "Platform keys on every model",
    ],
  },
};

/** What a credit buys, from production usage (2026-10-15). Rounded and stated as "about",
 *  because real runs vary with prompt length, image size and clip settings. Video and 3D are the
 *  most exact, since fal prices them per clip second and per model. */
export const CREDIT_GUIDE = [
  { what: "A text run", credits: "under 1" },
  { what: "A voice clip", credits: "about 3" },
  { what: "A 3D model", credits: "10" },
  { what: "An image", credits: "about 13" },
  { what: "A 5-second video", credits: "about 54" },
] as const;

/** The plan badge + one-line summary in Settings → Billing. */
export const PLAN_COPY: Record<string, { label: string; blurb: string }> = {
  free: {
    label: "Free",
    blurb: "1 workspace, 3 projects and 100 credits a month. Code export is a Plus feature.",
  },
  beta: {
    label: "Beta",
    blurb: "Early access on Starter's allowance: 500 credits a month and 10 projects.",
  },
  starter: {
    label: "Starter",
    blurb: "500 credits a month, 10 projects and 2 GB of storage. Code export is a Plus feature.",
  },
  plus: {
    label: "Plus",
    blurb:
      "1,000 credits a month, 3 workspaces and 20 projects pooled across them, and code export: the generated Python is yours to edit, download and run anywhere.",
  },
};
