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

/** The pricing page FAQ. Each answer describes what billing does **today**; if the behaviour
 *  changes, change the answer in the same PR. Where it rests on a policy rather than on code,
 *  the comment beside it says so. */
export const PRICING_FAQ = [
  {
    q: "What happens when I upgrade?",
    // `billing.set_plan` clears the month's grant anchor on an upgrade, so the top-up runs now.
    a: "Your new plan starts straight away. Your credits are topped up to the new plan's monthly allowance on the spot, so going from Starter to Plus mid-month takes you to 1,000 credits, not next month. Stripe charges only the difference for the rest of the billing period.",
  },
  {
    q: "What happens when I downgrade or cancel?",
    // `cancel_at_period_end` keeps the plan until the period ends; over-cap work is locked, not
    // deleted (downgrade path, PRs #63/#66); retention keeps the paid window for 7 more days.
    a: "You keep your current plan until the end of the period you've paid for. After that, anything over the new plan's limits becomes read-only rather than deleted: you can still open and export it, and you get it back by upgrading or by deleting down to the limit. Your agents' memory of past conversations is kept for 7 more days at the old retention before the new plan's applies.",
  },
  {
    q: "What if I still have credits when I downgrade?",
    // `grant_monthly` only ever tops up, never down, so a leftover balance is never taken back.
    a: "You keep them. Credits you've been given are never taken back. You spend down what you have, and the smaller monthly top-up only starts again once your balance falls below the new plan's allowance.",
  },
  {
    q: "Do unused credits roll over?",
    a: "No. Each month your balance is topped up to your plan's allowance, so unused credits don't pile up from month to month. Whatever you have left when the month turns is simply topped back up to the full amount.",
  },
  {
    q: "Can I top up credits?",
    // Policy, not code: the ledger has a `topup` kind but nothing sells one yet.
    a: "Not yet. If you run out mid-month you can upgrade, wait for the monthly reset, or add your own OpenAI key in Settings: text, image and voice runs on your own key cost no credits at all. Video and 3D always run on our keys and always use credits.",
  },
  {
    q: "Can I get a refund?",
    // Policy, not code: placeholder until the founder decides the refund policy.
    a: "You can cancel any time from Billing, and you keep your plan until the end of the period you've paid for. If something went wrong with a charge, get in touch and we'll sort it out.",
  },
  {
    q: "What is a credit?",
    a: "Credits measure what our AI providers charge when your agents run on our keys. A text run costs well under one credit; images, voice, 3D and video cost more. The table above shows typical costs.",
  },
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
