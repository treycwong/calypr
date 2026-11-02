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
STARTER_PRICE_ID_ENV = "STRIPE_STARTER_PRICE_ID"

#: Which env var holds each sellable plan's Stripe price. One map, read in both directions: by
#: checkout (plan → price) and by the webhook (price → plan). Before the retier the webhook
#: assumed any paid subscription was Plus, which is exactly the bug a second paid tier would hit
#: only in production.
_PRICE_ENV_BY_PLAN = {
    entitlements.STARTER: STARTER_PRICE_ID_ENV,
    entitlements.PLUS: PRICE_ID_ENV,
}


def secret_key() -> str:
    return os.getenv(SECRET_KEY_ENV, "")


def webhook_secret() -> str:
    return os.getenv(WEBHOOK_SECRET_ENV, "")


def plus_price_id() -> str:
    return os.getenv(PRICE_ID_ENV, "")


def price_id_for(plan: str) -> str:
    """The configured Stripe price for a sellable plan, or "" if it isn't set (or isn't sold)."""
    env = _PRICE_ENV_BY_PLAN.get(plan)
    return os.getenv(env, "") if env else ""


def plan_for_price(price: object) -> str | None:
    """The plan a Stripe price sells, or None if it is not one of ours.

    Takes a price id or a Price object. The configured ids decide first. Failing that, the
    `plan` tag each Calypr price carries in its Stripe metadata does, which keeps a subscription
    on a price that has since been rotated out of the env from losing its entitlement."""
    price_id = price if isinstance(price, str) else getattr(price, "id", None)
    for plan in entitlements.PAID_PLANS:
        if price_id and price_id == price_id_for(plan):
            return plan
    metadata = getattr(price, "metadata", None)
    tagged = getattr(metadata, "plan", None) if metadata is not None else None
    if tagged in entitlements.PAID_PLANS:
        return str(tagged)
    return None


def plan_for_subscription(sub: object) -> str | None:
    """The plan a Subscription pays for, read off its first item's price.

    A subscription whose price we cannot place falls back to **Plus**, with a warning. Every
    subscription sold before the retier was Plus at $20, and that price carries no `plan` tag;
    leaving the plan untouched there would cut off someone who is paying. None only when there is
    no price to read at all."""
    try:
        # Subscript access, not `.items`, which on a StripeObject is the dict method.
        items = sub["items"].data  # type: ignore[index]
    except (KeyError, AttributeError, TypeError):
        return None
    if not items:
        return None
    price = getattr(items[0], "price", None)
    if price is None:
        return None
    plan = plan_for_price(price)
    if plan is None:
        log.warning(
            "subscription %s is on unknown price %s; treating it as plus",
            getattr(sub, "id", "?"), getattr(price, "id", price),
        )
        return entitlements.PLUS
    return plan


def is_configured() -> bool:
    """Whether billing is switched on. Unset (dev, CI, and prod until launch) ⇒ the routes 503
    rather than half-working, so a missing key can't look like a payment failure."""
    return bool(secret_key() and webhook_secret())


#: Subscription statuses that entitle an account to the plan it pays for.
#:
#: `past_due` is deliberately included: the card failed but Stripe is still retrying, and the
#: subscription is not over. Cutting someone off mid-dunning — while they may well fix the card
#: — turns a billing hiccup into a support ticket and a churn event. `unpaid`/`canceled` are
#: where Stripe has given up, and that is where the entitlement ends.
ENTITLING_STATUSES = frozenset({"active", "trialing", "past_due"})

#: Statuses that end the entitlement. Anything not in either set (e.g. `incomplete`, a checkout
#: that was never completed) leaves the plan untouched — it was never granted in the first place.
ENDING_STATUSES = frozenset({"canceled", "unpaid", "incomplete_expired"})


def plan_for_status(status: str, paid_plan: str | None = None) -> str | None:
    """The plan a subscription status implies, or None to leave the plan alone.

    `paid_plan` is what the subscription's price buys (`plan_for_subscription`). An entitling
    status grants that; without one (an event that carried no price) it falls back to Plus, the
    only tier there was before the retier."""
    if status in ENTITLING_STATUSES:
        return paid_plan or entitlements.PLUS
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
    if entitlements.is_upgrade(account.plan, plan):
        # Let this month's grant run again, so the bigger allowance arrives now rather than
        # next month. `grant_monthly` only ever tops up, so this can't take credits away.
        account.grant_cycle_anchor = None
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
