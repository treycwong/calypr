"""Stripe configuration and the subscription → plan mapping.

Kept out of the router so the *decisions* are testable without a request: which subscription
statuses count as paid, and how a Stripe customer maps back to an account.

Billing hangs off the **account**, not the workspace (0016) — one subscription covers all the
workspaces a user owns, which is the whole point of letting them have more than one.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.db.models import Account

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


#: Subscription statuses that entitle an account to Plus.
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


def account_for_customer(session: Session, customer_id: str | None) -> Account | None:
    """The account billing as this Stripe customer, if we know it."""
    if not customer_id:
        return None
    return session.scalar(select(Account).where(Account.stripe_customer_id == customer_id))


def set_plan(account: Account, plan: str) -> bool:
    """Move an account onto `plan`. Returns whether anything changed. Callers commit.

    `beta` is never overwritten by a *downgrade*: the beta cohort was granted access by hand and
    doesn't have a subscription, so a stray `customer.subscription.deleted` for a customer that
    somehow maps to them must not take it away. An upgrade to `plus` is allowed from any tier —
    they paid.

    Stamps `plan_changed_at` on a real change, and **only** on a real change. That timestamp opens
    the grace window in `entitlements.retention_days`, so re-stamping it on a no-op would let a
    redelivered webhook — or a `cancel_at_period_end` flip, which arrives as an update with the
    same entitling status — quietly extend someone's retention forever. The early returns above
    are what keep that honest."""
    if plan == entitlements.FREE and account.plan == entitlements.BETA:
        log.info("ignoring downgrade of a beta account %s", account.id)
        return False
    if account.plan == plan:
        return False
    account.plan = plan
    account.plan_changed_at = datetime.now(UTC)
    return True


def is_missing_resource(exc: stripe.StripeError) -> bool:
    """True when Stripe rejected a request because the thing it names doesn't exist under the
    current key. Matched on the `resource_missing` code rather than the message text, so it
    survives Stripe's copy changes."""
    return getattr(exc, "code", None) == "resource_missing"


def is_missing_customer(exc: stripe.StripeError) -> bool:
    """`is_missing_resource`, narrowed to the *customer* param — the classic wedge where an
    account carries a **test-mode** customer id and a **live** key is used (or the customer was
    deleted in the dashboard).

    Lives here rather than in the router because the deletion path needs the same judgement and
    two copies of "is this the recoverable Stripe error?" would drift — the copy that drifted
    would be the one deciding whether it is safe to delete someone's account."""
    return is_missing_resource(exc) and getattr(exc, "param", None) == "customer"


def cancel_subscription(account: Account) -> bool:
    """End this account's subscription **immediately**. True if something was cancelled.

    Immediate, not `cancel_at_period_end`: an account that no longer exists must not carry a live
    subscription for another three weeks. That does forfeit the paid remainder unprorated, which
    is a real cost to the user — so the delete dialog has to say so before they confirm.

    Raises `stripe.StripeError` if the cancellation genuinely failed. The caller **must** treat
    that as fatal and change nothing: an account deleted while its subscription keeps charging is
    the one outcome we can't let through, and since nothing has been written yet, a retry is free.

    A subscription Stripe says is already gone counts as success — the goal is "not billing", and
    it isn't. We deliberately do **not** delete the Stripe *customer*: invoices and tax records
    have to survive the account that generated them.
    """
    sub_id = account.stripe_subscription_id
    if not sub_id:
        return False  # free, beta, or already cancelled — nothing to do
    try:
        stripe.Subscription.cancel(sub_id, api_key=secret_key())
    except stripe.StripeError as exc:
        if not is_missing_resource(exc):
            raise
        log.warning(
            "subscription %s already gone at Stripe for account %s; treating as cancelled",
            sub_id, account.id,
        )
    return True
