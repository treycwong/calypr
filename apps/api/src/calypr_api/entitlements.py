"""What a workspace's plan entitles it to.

One module so gating rules are a single edit rather than string comparisons scattered across
routers and components. `workspace.plan` is `free | beta | plus` (see 0008_plan_and_waitlist);
billing — Stripe, the credit ledger, the 402 paywall — lands in Weeks 9–10 per `PRICING-SPEC.md`.

The distinction these functions encode: **`beta` gates on our confidence, `plus` gates on value
capture.** They are different axes and shouldn't be conflated — but a feature can sit on both, and
code export now does.

**Reversed 2026-07-22:** this module previously argued the reverse round-trip would graduate to
free for everyone, because it was the product's core "no ceiling" promise and its parser was
headed for OSS. The product is now closed — no OSS launch — and **code export is a paid feature**.
`has_roundtrip` therefore never graduates. Paid differentiation still *also* lives on capacity
(projects, credits, platform-key model access) per `PRICING-SPEC.md` §1; export is the
qualitative differentiator on top of it.
"""

from __future__ import annotations

from datetime import UTC, datetime

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
    """Whether code export — the Code tab's editable mode and "Apply to canvas" — is available.

    A **paid entitlement**, not a temporary gate: `plus` buys it, and `beta` keeps it for the
    cohort already using it (we don't take a shipped feature back off them). It does not graduate
    to `return True`; see the module docstring for the decision that reversed."""
    return plan in (BETA, PLUS)


def requires_own_key(plan: str | None) -> bool:
    """Whether this plan must bring its own provider key to run a canvas.

    Free is **BYO-key only** for node runs (`PRICING-SPEC.md` §1), which is exactly what
    `/pricing` sells it as — "Free to build and run with your own API key". Its monthly credits
    are an *assistant* budget, not a run budget.

    Enforced rather than implied, because until 2026-07-24 it was only implied: the shipped
    ledger let a Free workspace spend its 100 credits on platform-key node runs nobody had
    advertised, which is the revenue leak `TODO` §2 tracked. `beta` and `plus` pay for platform
    access and are unaffected."""
    return (plan or FREE) == FREE


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


def _unredeemed_invite(session: Session, email: str | None) -> Waitlist | None:
    """The invite row for this address that hasn't been spent yet, if any."""
    if not email:
        return None
    return session.scalar(
        select(Waitlist).where(
            Waitlist.email == email.strip().lower(),
            Waitlist.invited_at.is_not(None),
            Waitlist.granted_at.is_(None),
        )
    )


def grant_beta_if_invited(session: Session, workspace: Workspace, email: str | None) -> bool:
    """Upgrade a `free` workspace to `beta` when its owner has an **unredeemed** invite.

    This is what makes an invite self-serve: you stamp an address, they sign in with it, and the
    beta switches on by itself — no looking up workspace ids by hand.

    The invite is a one-time key, and `granted_at` is what spends it. Before that existed this
    re-ran on every sign-in, so a demotion could never stick: move someone from `beta` back to
    `free` — a trial ending, or the beta itself ending — and their next login silently restored
    it. The admin route was documented as authoritative and quietly wasn't.

    Still one-way and only from `free`: it never downgrades, and never touches a `plus`
    workspace. Returns whether it changed anything. Callers commit."""
    if workspace.plan != FREE:
        return False
    invite = _unredeemed_invite(session, email)
    if invite is None:
        return False
    workspace.plan = BETA
    invite.granted_at = datetime.now(UTC)
    return True
