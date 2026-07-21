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

from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api.db.models import Waitlist, Workspace

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


def is_invited(session: Session, email: str | None) -> bool:
    """Whether this address is on the beta invite list.

    The list is just `waitlist` rows with `invited_at` set — the same table the landing form
    writes to. So "invite someone" means stamping their existing signup, or adding a row for
    someone who never joined the waitlist. One list, no second place to keep in sync."""
    if not email:
        return False
    return (
        session.scalar(
            select(Waitlist.id).where(
                Waitlist.email == email.strip().lower(),
                Waitlist.invited_at.is_not(None),
            )
        )
        is not None
    )


def grant_beta_if_invited(session: Session, workspace: Workspace, email: str | None) -> bool:
    """Upgrade a `free` workspace to `beta` when its owner's email has been invited.

    This is what makes an invite self-serve: you stamp an address, they sign in with it, and the
    beta switches on by itself — no looking up workspace ids by hand.

    Deliberately one-way and only from `free`: it never downgrades, and never touches a `plus`
    workspace, so the manual admin route stays authoritative for anything unusual. Returns
    whether it changed anything. Callers commit."""
    if workspace.plan != FREE or not is_invited(session, email):
        return False
    workspace.plan = BETA
    return True
