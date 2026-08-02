"""What an account's plan entitles it to.

One module so gating rules are a single edit rather than string comparisons scattered across
routers and components. `account.plan` is `free | beta | plus` — it lived on `workspace` until
0016 moved it, because a plan that multiplies with workspaces isn't a plan.

Two kinds of entitlement live here. **Capacity** is the `LIMITS` table: projects, workspaces,
credits, storage — all pooled per account, so a second workspace is somewhere to organise work
rather than more of it. **Features** are predicates like `has_roundtrip`.

The distinction these functions encode: **`beta` gates on our confidence, `plus` gates on value
capture.** They are different axes and shouldn't be conflated — but a feature can sit on both, and
code export now does.

**Reversed 2026-07-22:** this module previously argued the reverse round-trip would graduate to
free for everyone, because it was the product's core "no ceiling" promise and its parser was
headed for OSS. The product is now closed — no OSS launch — and **code export is a paid feature**.
`has_roundtrip` therefore never graduates. Export is the qualitative differentiator on top of the
capacity limits below, per `PRICING-SPEC.md` §1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api.db.models import Account, Waitlist

FREE = "free"
BETA = "beta"
PLUS = "plus"

PLANS = (FREE, BETA, PLUS)


@dataclass(frozen=True)
class Limits:
    """Everything a plan is allowed, in one row per plan.

    Capacity used to be spread across four modules and a marketing page, which is how
    `/pricing` came to advertise a project cap that no code enforced. One table means adding a
    limit is one edit and forgetting to enforce one is visible."""

    #: Saved agents, **pooled across all of an account's workspaces** — not per workspace, so a
    #: second workspace is somewhere to organise work, never more of it.
    projects: int
    workspaces: int
    #: Credits granted per calendar month, pooled the same way. `credits.MONTHLY_GRANT` derives
    #: from this.
    monthly_credits: int
    #: Pooled storage. **Displayed, not enforced** — see `storage_usage.py` for why a byte cap
    #: can't be honestly enforced yet, and what bounds storage instead.
    storage_bytes: int
    #: How long LangGraph checkpoints survive. This is the mechanism that actually bounds
    #: storage; the byte figure above is how a user sees it working.
    checkpoint_ttl_days: int
    #: Code export — the Code tab's editable mode and "Apply to canvas".
    roundtrip: bool


#: `beta` matches `plus` on capacity: the cohort was invited to use the product properly, and
#: metering them onto a smaller pool would make their feedback about the wrong product.
LIMITS: dict[str, Limits] = {
    FREE: Limits(
        projects=3,
        workspaces=1,
        monthly_credits=100,  # assistant only
        storage_bytes=500 * 1024**2,  # 500 MB
        checkpoint_ttl_days=7,
        roundtrip=False,
    ),
    BETA: Limits(
        projects=20,
        workspaces=3,
        monthly_credits=2_000,
        storage_bytes=5 * 1024**3,  # 5 GB
        checkpoint_ttl_days=30,
        roundtrip=True,
    ),
    PLUS: Limits(
        projects=20,
        workspaces=3,
        monthly_credits=2_000,
        storage_bytes=5 * 1024**3,  # 5 GB
        checkpoint_ttl_days=30,
        roundtrip=True,
    ),
}


def limits(plan: str | None) -> Limits:
    """What this plan allows. An unknown or missing plan gets Free — fail to the smallest set."""
    return LIMITS.get(plan or FREE, LIMITS[FREE])


def is_valid_plan(plan: str) -> bool:
    return plan in PLANS


def has_roundtrip(plan: str | None) -> bool:
    """Whether code export — the Code tab's editable mode and "Apply to canvas" — is available.

    A **paid entitlement**, not a temporary gate: `plus` buys it, and `beta` keeps it for the
    cohort already using it (we don't take a shipped feature back off them). It does not graduate
    to `return True`; see the module docstring for the decision that reversed."""
    return limits(plan).roundtrip


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


def grant_beta_if_invited(session: Session, account: Account, email: str | None) -> bool:
    """Upgrade a `free` account to `beta` when its owner has an **unredeemed** invite.

    This is what makes an invite self-serve: you stamp an address, they sign in with it, and the
    beta switches on by itself — no looking up workspace ids by hand.

    The invite is a one-time key, and `granted_at` is what spends it. Before that existed this
    re-ran on every sign-in, so a demotion could never stick: move someone from `beta` back to
    `free` — a trial ending, or the beta itself ending — and their next login silently restored
    it. The admin route was documented as authoritative and quietly wasn't.

    Still one-way and only from `free`: it never downgrades, and never touches a `plus`
    account. Returns whether it changed anything. Callers commit."""
    if account.plan != FREE:
        return False
    invite = _unredeemed_invite(session, email)
    if invite is None:
        return False
    account.plan = BETA
    invite.granted_at = datetime.now(UTC)
    return True
