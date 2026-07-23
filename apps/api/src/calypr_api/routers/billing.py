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

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from calypr_api import billing
from calypr_api.db.models import StripeEvent, Workspace
from calypr_api.db.session import SessionLocal
from calypr_api.deps import Tenant, tenant
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import BillingStatus, CheckoutSession

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
    existing_customer = workspace.stripe_customer_id
    try:
        checkout = stripe.checkout.Session.create(
            api_key=billing.secret_key(),
            mode="subscription",
            line_items=[{"price": billing.plus_price_id(), "quantity": 1}],
            # Carries the workspace through Stripe and back on the completed event — how the
            # payment is attributed without trusting anything the browser said.
            client_reference_id=str(t.workspace_id),
            # Reuse the customer if this workspace has paid before, so a re-subscribe doesn't
            # create a second customer for the same tenant (the mapping is unique).
            customer=existing_customer or None,
            customer_email=t.email if not existing_customer and t.email else None,
            success_url=f"{origin}/dashboard/settings?upgraded=1",
            cancel_url=f"{origin}/pricing",
        )
    except stripe.StripeError:
        log.exception("stripe checkout session creation failed")
        raise HTTPException(status_code=502, detail="could not start checkout") from None

    posthog_client.capture(
        "checkout_started",
        distinct_id=str(t.workspace_id),
        properties={"workspace_id": str(t.workspace_id)},
    )
    return CheckoutSession(url=checkout.url or "")


def _field(obj: object, name: str) -> str | None:
    """Read an optional field off a Stripe object.

    `StripeObject` is **not** a dict in the v15 SDK — it has no `.get()`, and `obj["missing"]`
    raises KeyError — so a webhook payload that legitimately omits a field (a checkout session
    with no `client_reference_id`, say) needs this rather than dict access."""
    value = getattr(obj, name, None)
    return str(value) if value is not None else None


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
        status = "canceled" if kind.endswith(".deleted") else (_field(data, "status") or "")
        plan = billing.plan_for_status(status)
        if plan and billing.set_plan(workspace, plan):
            session.commit()
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
        # Renewal. The plan is already `plus` in the normal case; this re-asserts it so a
        # workspace can't drift out of entitlement while it is genuinely paying. The monthly
        # credit grant hangs here once the ledger exists.
        workspace = billing.workspace_for_customer(session, _field(data, "customer"))
        if workspace is not None and billing.set_plan(workspace, "plus"):
            session.commit()
            log.info("workspace %s re-asserted to plus on renewal", workspace.id)
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
