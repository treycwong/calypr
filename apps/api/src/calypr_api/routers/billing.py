"""Stripe billing: the checkout hand-off and the webhook that grants the plan.

The webhook is the only thing in this codebase that changes an entitlement based on an *inbound*
request, so it is written defensively:

- **Signature first.** The raw request body is verified against the endpoint's signing secret
  before it is parsed. Anyone can POST here; only Stripe can sign.
- **Idempotent.** Stripe delivers at least once. The `evt_…` id is inserted first and a
  duplicate short-circuits, because the handlers are not naturally replay-safe.
- **Retry only when retrying could help.** A transient failure returns 500 so Stripe backs off
  and tries again; a permanently unusable event (a customer we can't map) returns 200, because
  retrying it for three days changes nothing and buries the real failures.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from calypr_api import billing, credits
from calypr_api.db.models import StripeEvent, Workspace
from calypr_api.db.session import SessionLocal
from calypr_api.deps import Tenant, tenant
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    BillingStatus,
    CheckoutSession,
    PortalSession,
    SubscriptionInfo,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

#: The events this endpoint acts on. Anything else is recorded and ignored — a destination
#: configured with extra events shouldn't 500, it should just be quiet.
HANDLED = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


@router.get("/status", response_model=BillingStatus)
def billing_status() -> BillingStatus:
    """Whether checkout can actually take a payment right now.

    Lets the checkout page render the truth on first paint instead of making someone click
    "pay" to discover billing isn't on. Deliberately unauthenticated and secret-free: it
    reports only that keys are *present*, never anything about them."""
    return BillingStatus(enabled=billing.is_configured() and bool(billing.plus_price_id()))


@router.post("/checkout", response_model=CheckoutSession)
def create_checkout(request: Request, t: Tenant = Depends(tenant)) -> CheckoutSession:
    """Start a Stripe Checkout Session for Plus and hand back its URL.

    `client_reference_id` carries the workspace id through Stripe and back on the completed
    event — it is how the payment is attributed without trusting anything the browser says."""
    if not billing.is_configured() or not billing.plus_price_id():
        raise HTTPException(status_code=503, detail="billing is not configured")

    workspace = t.session.get(Workspace, t.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")

    def _session(customer: str | None):
        return stripe.checkout.Session.create(
            api_key=billing.secret_key(),
            mode="subscription",
            line_items=[{"price": billing.plus_price_id(), "quantity": 1}],
            # Carries the workspace through Stripe and back on the completed event — how the
            # payment is attributed without trusting anything the browser said.
            client_reference_id=str(t.workspace_id),
            # Reuse the customer if this workspace has paid before, so a re-subscribe doesn't
            # create a second customer for the same tenant (the mapping is unique).
            customer=customer or None,
            customer_email=t.email if not customer and t.email else None,
            success_url=f"{origin}/dashboard/settings?upgraded=1",
            cancel_url=f"{origin}/pricing",
        )

    existing_customer = workspace.stripe_customer_id
    try:
        checkout = _session(existing_customer)
    except stripe.InvalidRequestError as exc:
        # A stored customer that Stripe no longer knows (a test-mode customer under a live key,
        # or one deleted in the dashboard) would wedge this workspace on every upgrade attempt.
        # Forget it and retry once with a fresh customer so the user is never permanently stuck.
        if not (existing_customer and _is_missing_customer(exc)):
            log.exception("stripe checkout session creation failed")
            raise HTTPException(status_code=502, detail="could not start checkout") from None
        log.warning(
            "stale stripe customer %s on workspace %s; clearing and retrying checkout",
            existing_customer, t.workspace_id,
        )
        _forget_customer(workspace)
        t.session.commit()
        try:
            checkout = _session(None)
        except stripe.StripeError:
            log.exception("stripe checkout retry with a fresh customer failed")
            raise HTTPException(status_code=502, detail="could not start checkout") from None
    except stripe.StripeError:
        log.exception("stripe checkout session creation failed")
        raise HTTPException(status_code=502, detail="could not start checkout") from None

    posthog_client.capture(
        "checkout_started",
        distinct_id=str(t.workspace_id),
        properties={"workspace_id": str(t.workspace_id)},
    )
    return CheckoutSession(url=checkout.url or "")


@router.get("/subscription", response_model=SubscriptionInfo)
def get_subscription(t: Tenant = Depends(tenant)) -> SubscriptionInfo:
    """The plan + cycle state the Billing tab renders. Reads mirrored columns only — no live
    Stripe call — so the tab paints instantly. `portal_available` gates the "Manage billing"
    button: it needs both a Stripe customer (something to manage) and billing switched on."""
    workspace = t.session.get(Workspace, t.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return SubscriptionInfo(
        plan=workspace.plan,
        current_period_end=workspace.current_period_end,
        cancel_at_period_end=workspace.cancel_at_period_end,
        portal_available=bool(workspace.stripe_customer_id) and billing.is_configured(),
    )


@router.post("/portal", response_model=PortalSession)
def create_portal(request: Request, t: Tenant = Depends(tenant)) -> PortalSession:
    """Open Stripe's hosted Customer Portal for this workspace and hand back its URL.

    The portal is where cancel / plan change / payment-method / invoice-history live — none of
    that UI is ours, and no card data ever reaches us. A workspace with no `stripe_customer_id`
    has nothing to manage (it never subscribed), so this 400s rather than creating an empty
    portal session."""
    if not billing.is_configured():
        raise HTTPException(status_code=503, detail="billing is not configured")

    workspace = t.session.get(Workspace, t.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if not workspace.stripe_customer_id:
        raise HTTPException(status_code=400, detail="no subscription to manage")

    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    try:
        portal = stripe.billing_portal.Session.create(
            api_key=billing.secret_key(),
            customer=workspace.stripe_customer_id,
            return_url=f"{origin}/dashboard/settings?tab=billing",
        )
    except stripe.InvalidRequestError as exc:
        # The stored customer is gone (test customer under a live key, or deleted in Stripe).
        # There's nothing to manage, so forget the dead mapping — the tab will fall back to the
        # Upgrade CTA on its next load — and tell the client to re-subscribe rather than 502.
        if not _is_missing_customer(exc):
            log.exception("stripe billing portal session creation failed")
            raise HTTPException(status_code=502, detail="could not open billing portal") from None
        log.warning(
            "stale stripe customer %s on workspace %s; clearing (portal)",
            workspace.stripe_customer_id, t.workspace_id,
        )
        _forget_customer(workspace)
        t.session.commit()
        raise HTTPException(
            status_code=409, detail="subscription is no longer valid — please re-subscribe"
        ) from None
    except stripe.StripeError:
        log.exception("stripe billing portal session creation failed")
        raise HTTPException(status_code=502, detail="could not open billing portal") from None

    posthog_client.capture(
        "billing_portal_opened",
        distinct_id=str(t.workspace_id),
        properties={"workspace_id": str(t.workspace_id)},
    )
    return PortalSession(url=portal.url or "")


def _field(obj: object, name: str) -> str | None:
    """Read an optional field off a Stripe object.

    `StripeObject` is **not** a dict in the v15 SDK — it has no `.get()`, and `obj["missing"]`
    raises KeyError — so a webhook payload that legitimately omits a field (a checkout session
    with no `client_reference_id`, say) needs this rather than dict access."""
    value = getattr(obj, name, None)
    return str(value) if value is not None else None


def _epoch(value: object) -> datetime | None:
    """Turn a Unix timestamp (Stripe sends period bounds as integer seconds) into an aware UTC
    datetime, or None if absent."""
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def _bool(obj: object, name: str) -> bool:
    """Read an optional boolean field off a Stripe object, defaulting to False when absent."""
    return bool(getattr(obj, name, False))


def _period_end(sub: object) -> datetime | None:
    """When the current paid period ends, off a Subscription object.

    Stripe moved `current_period_end` off the Subscription and onto its items in recent API
    versions (this account is on `2026-06-24.dahlia`, where the top-level field is gone). Read
    the first item's value — a single-price subscription like Calypr Plus has one item and all
    items share a period — and fall back to the top-level field for older API versions."""
    top = getattr(sub, "current_period_end", None)
    if top is not None:
        return _epoch(top)
    try:
        # Subscript access, not `.items` — on a StripeObject `.items` is the dict method.
        items = sub["items"].data
    except (KeyError, AttributeError, TypeError):
        return None
    if not items:
        return None
    return _epoch(getattr(items[0], "current_period_end", None))


def _mirror_cycle(workspace: Workspace, sub: object) -> None:
    """Copy a Subscription's cycle fields onto the workspace row — the three columns the Billing
    tab reads. Used from both the subscription-event branch and, to beat event-ordering races,
    the checkout branch."""
    workspace.stripe_subscription_id = _field(sub, "id")
    workspace.current_period_end = _period_end(sub)
    workspace.cancel_at_period_end = _bool(sub, "cancel_at_period_end")


def _is_missing_customer(exc: stripe.StripeError) -> bool:
    """True when Stripe rejected a request because the referenced `customer` doesn't exist under
    the current key — the classic wedge where a workspace carries a *test-mode* customer id and a
    *live* key is used (or the customer was deleted in Stripe). Matched on the `resource_missing`
    code for the `customer` param, not the message text, so it survives copy changes."""
    return (
        getattr(exc, "code", None) == "resource_missing"
        and getattr(exc, "param", None) == "customer"
    )


def _forget_customer(workspace: Workspace) -> None:
    """Drop a workspace's now-invalid Stripe customer mapping and its stale cycle fields, so the
    next checkout mints a fresh customer instead of failing on the dead one forever."""
    workspace.stripe_customer_id = None
    workspace.stripe_subscription_id = None
    workspace.current_period_end = None
    workspace.cancel_at_period_end = False


def _apply(session: Session, event: stripe.Event) -> None:
    """Act on one verified event. Raises only on failures worth a retry."""
    data = event.data.object  # type: ignore[union-attr]
    kind = event.type

    if kind == "checkout.session.completed":
        # The one event that can *establish* the mapping: everything later refers to the
        # customer, and this is where we learn which workspace that customer is.
        workspace_id = _field(data, "client_reference_id")
        customer_id = _field(data, "customer")
        if not workspace_id:
            log.warning("checkout.session.completed with no client_reference_id: %s", event.id)
            return
        workspace = session.get(Workspace, workspace_id)
        if workspace is None:
            log.warning("checkout completed for unknown workspace %s", workspace_id)
            return
        if customer_id:
            workspace.stripe_customer_id = customer_id
        billing.set_plan(workspace, "plus")
        # Populate the cycle fields at the authoritative "this workspace is now subscribed"
        # moment. Stripe doesn't guarantee event ordering, so `customer.subscription.created`
        # commonly arrives *before* this event maps the customer — and is then dropped as
        # "unmapped", leaving the cycle blank forever (Stripe never redelivers it). Retrieving
        # the subscription here closes that race. Best-effort: the plan + credits below matter
        # more, and the cycle self-heals on the next `subscription.updated`.
        if sub_id := _field(data, "subscription"):
            try:
                sub = stripe.Subscription.retrieve(sub_id, api_key=billing.secret_key())
                _mirror_cycle(workspace, sub)
            except stripe.StripeError:
                log.warning("could not retrieve subscription %s for cycle mirror", sub_id)
        # Grant immediately: `invoice.paid` usually accompanies the first payment, but relying
        # on ordering would leave a new subscriber with a Plus plan and no credits if it lands
        # first or is delayed. `grant_monthly` is idempotent per cycle, so a double is a no-op.
        credits.grant_monthly(session, workspace, ref_id=f"checkout:{event.id}")
        session.commit()
        posthog_client.capture(
            "subscription_activated",
            distinct_id=str(workspace.id),
            properties={"workspace_id": str(workspace.id)},
        )
        log.info("workspace %s upgraded to plus", workspace.id)
        return

    if kind.startswith("customer.subscription."):
        customer_id = _field(data, "customer")
        workspace = billing.workspace_for_customer(session, customer_id)
        if workspace is None:
            # Not an error worth retrying: a customer we have no mapping for (created in the
            # dashboard by hand, or belonging to another environment) will never map on retry.
            log.warning("subscription event for unmapped customer %s", customer_id)
            return
        deleted = kind.endswith(".deleted")
        status = "canceled" if deleted else (_field(data, "status") or "")
        plan = billing.plan_for_status(status)
        changed = bool(plan) and billing.set_plan(workspace, plan)
        # Mirror the cycle fields the Billing tab reads. On `.deleted` the subscription is over,
        # so clear them; otherwise reflect the current period end and whether a cancel is pending
        # for the end of it (both set from the portal). Always persisted — a `cancel_at_period_end`
        # flip arrives as `.updated` with the same entitling status, so the plan doesn't change
        # but the tab must still learn the subscription is winding down.
        if deleted:
            workspace.stripe_subscription_id = None
            workspace.current_period_end = None
            workspace.cancel_at_period_end = False
        else:
            _mirror_cycle(workspace, data)
        session.commit()
        if changed:
            log.info("workspace %s → %s (subscription %s)", workspace.id, plan, status)
        return

    if kind == "invoice.payment_failed":
        # Deliberately does *not* downgrade. Stripe is still retrying the card; the subscription
        # is what says whether it's over, and that arrives as `customer.subscription.updated`.
        customer_id = _field(data, "customer")
        workspace = billing.workspace_for_customer(session, customer_id)
        log.warning(
            "invoice payment failed for customer %s (workspace %s)",
            customer_id,
            workspace.id if workspace else "unknown",
        )
        if workspace is not None:
            posthog_client.capture(
                "invoice_payment_failed",
                distinct_id=str(workspace.id),
                properties={"workspace_id": str(workspace.id)},
            )
        return

    if kind == "invoice.paid":
        # Renewal — and the moment the month's credits are issued. Re-asserting the plan keeps a
        # workspace from drifting out of entitlement while it is genuinely paying.
        workspace = billing.workspace_for_customer(session, _field(data, "customer"))
        if workspace is None:
            return
        changed = billing.set_plan(workspace, "plus")
        # The invoice id is the grant's idempotency key: Stripe delivers at-least-once, and a
        # redelivery that granted again would be free credits every month, forever.
        granted = credits.grant_monthly(
            session, workspace, ref_id=_field(data, "id") or event.id
        )
        if changed or granted:
            session.commit()
            log.info(
                "workspace %s renewal (plan_changed=%s credits_granted=%s)",
                workspace.id, changed, granted,
            )
        return


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, bool]:
    """Verify, deduplicate, apply.

    Note there is no `Depends(get_session)`: the session is opened *after* the signature
    verifies, so an unsigned POST — which anyone on the internet can send — costs a hash rather
    than a database connection.
    """
    if not billing.is_configured():
        raise HTTPException(status_code=503, detail="billing is not configured")

    # The *raw* bytes: the signature covers exactly what Stripe sent, so parsing or re-encoding
    # first would break verification.
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature or "", billing.webhook_secret()
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed payload") from None
    except stripe.SignatureVerificationError:
        # Someone POSTing here without the signing secret — or a secret/endpoint mismatch.
        log.warning("rejected a webhook with a bad signature")
        raise HTTPException(status_code=400, detail="bad signature") from None

    with SessionLocal() as session:
        # Idempotency before side effects: the insert is the check, so concurrent redeliveries
        # can't both get through.
        session.add(StripeEvent(id=event.id, type=event.type))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            log.info("ignoring duplicate delivery of %s", event.id)
            return {"received": True}

        if event.type not in HANDLED:
            return {"received": True}

        try:
            _apply(session, event)
        except Exception:
            session.rollback()
            # Let Stripe retry — but the idempotency row is already committed, so the retry
            # would short-circuit on it. Drop it so the next delivery gets a real attempt.
            session.query(StripeEvent).filter(StripeEvent.id == event.id).delete()
            session.commit()
            log.exception("failed to apply %s (%s); asking Stripe to retry", event.type, event.id)
            raise HTTPException(status_code=500, detail="could not process event") from None

    return {"received": True}
