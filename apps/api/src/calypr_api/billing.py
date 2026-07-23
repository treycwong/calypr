"""Stripe configuration and the subscription → plan mapping.

Kept out of the router so the *decisions* are testable without a request: which subscription
statuses count as paid, and how a Stripe customer maps back to a workspace.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.db.models import Workspace

log = logging.getLogger(__name__)

#: Conventional Stripe names rather than `CALYPR_`-prefixed ones — these are what Stripe's own
#: docs, dashboards and CLI use, so an operator copying a key knows where it goes.
SECRET_KEY_ENV = "STRIPE_SECRET_KEY"
WEBHOOK_SECRET_ENV = "STRIPE_WEBHOOK_SECRET"
PRICE_ID_ENV = "STRIPE_PLUS_PRICE_ID"


def secret_key() -> str:
    return os.getenv(SECRET_KEY_ENV, "")


def webhook_secret() -> str:
    return os.getenv(WEBHOOK_SECRET_ENV, "")


def plus_price_id() -> str:
    return os.getenv(PRICE_ID_ENV, "")


def is_configured() -> bool:
    """Whether billing is switched on. Unset (dev, CI, and prod until launch) ⇒ the routes 503
    rather than half-working, so a missing key can't look like a payment failure."""
    return bool(secret_key() and webhook_secret())


#: Subscription statuses that entitle a workspace to Plus.
#:
#: `past_due` is deliberately included: the card failed but Stripe is still retrying, and the
#: subscription is not over. Cutting someone off mid-dunning — while they may well fix the card
#: — turns a billing hiccup into a support ticket and a churn event. `unpaid`/`canceled` are
#: where Stripe has given up, and that is where the entitlement ends.
ENTITLING_STATUSES = frozenset({"active", "trialing", "past_due"})

#: Statuses that end the entitlement. Anything not in either set (e.g. `incomplete`, a checkout
#: that was never completed) leaves the plan untouched — it was never granted in the first place.
ENDING_STATUSES = frozenset({"canceled", "unpaid", "incomplete_expired"})


def plan_for_status(status: str) -> str | None:
    """The plan a subscription status implies, or None to leave the plan alone."""
    if status in ENTITLING_STATUSES:
        return entitlements.PLUS
    if status in ENDING_STATUSES:
        return entitlements.FREE
    return None


def workspace_for_customer(session: Session, customer_id: str | None) -> Workspace | None:
    """The workspace billing as this Stripe customer, if we know it."""
    if not customer_id:
        return None
    return session.scalar(select(Workspace).where(Workspace.stripe_customer_id == customer_id))


def set_plan(workspace: Workspace, plan: str) -> bool:
    """Move a workspace onto `plan`. Returns whether anything changed. Callers commit.

    `beta` is never overwritten by a *downgrade*: the beta cohort was granted access by hand and
    doesn't have a subscription, so a stray `customer.subscription.deleted` for a customer that
    somehow maps to them must not take it away. An upgrade to `plus` is allowed from any tier —
    they paid."""
    if plan == entitlements.FREE and workspace.plan == entitlements.BETA:
        log.info("ignoring downgrade of a beta workspace %s", workspace.id)
        return False
    if workspace.plan == plan:
        return False
    workspace.plan = plan
    return True
