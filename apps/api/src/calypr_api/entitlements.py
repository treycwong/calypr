"""What a workspace's plan entitles it to.

One module so gating rules are a single edit rather than string comparisons scattered across
routers and components. `workspace.plan` is `free | beta | plus` (see 0008_plan_and_waitlist);
billing — Stripe, the credit ledger, the 402 paywall — lands in Weeks 9–10 per `PRICING-SPEC.md`.

The distinction these functions encode: **`beta` gates on our confidence, `plus` gates on value
capture.** They are different axes and shouldn't be conflated. A feature can be beta-gated while
it settles and still end up free for everyone — that is exactly the plan for the reverse
round-trip, which is the product's core "no ceiling" promise (and whose parser ships as OSS), not
a premium add-on. Paid differentiation lives on capacity — projects, credits, platform-key model
access — per `PRICING-SPEC.md` §1.
"""

from __future__ import annotations

FREE = "free"
BETA = "beta"
PLUS = "plus"

PLANS = (FREE, BETA, PLUS)


def is_valid_plan(plan: str) -> bool:
    return plan in PLANS


def has_roundtrip(plan: str | None) -> bool:
    """Whether the reverse round-trip UI ("Apply to canvas") is available.

    Temporarily beta-gated while it proves out in the wild. When it graduates, this becomes
    `return True` — one line, one place."""
    return plan in (BETA, PLUS)
