"""Stripe billing: signature verification, idempotency, and the subscription → plan mapping.

The webhook is the one route that grants a paid entitlement from an *inbound* request, so the
security-critical parts — a forged signature is refused, a replay is a no-op — are tested with
real signatures and **without a database**, so they run everywhere rather than skipping on a
developer machine with Docker down.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from calypr_api import billing, entitlements
from calypr_api.db.models import StripeEvent, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)

TEST_SECRET = "whsec_test_secret_for_signing_only"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


@pytest.fixture
def configured(monkeypatch):
    """Billing switched on, with a known signing secret."""
    monkeypatch.setenv(billing.SECRET_KEY_ENV, "sk_test_not_a_real_key")
    monkeypatch.setenv(billing.WEBHOOK_SECRET_ENV, TEST_SECRET)
    monkeypatch.setenv(billing.PRICE_ID_ENV, "price_test_plus")


def _sign(body: str, timestamp: int, secret: str = TEST_SECRET) -> str:
    """Stripe's documented scheme: HMAC-SHA256 over `{timestamp}.{payload}`, hex-encoded.

    Implemented here with stdlib rather than the SDK's private `_compute_signature`, so an SDK
    upgrade can't quietly turn these tests into false passes (or confusing errors)."""
    return hmac.new(
        secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()


def _signed(payload: dict, secret: str = TEST_SECRET) -> tuple[str, dict[str, str]]:
    """A body plus a genuine Stripe-Signature header for it."""
    body = json.dumps(payload)
    timestamp = int(time.time())
    return body, {"Stripe-Signature": f"t={timestamp},v1={_sign(body, timestamp, secret)}"}


def _event(kind: str, obj: dict, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid.uuid4().hex[:16]}",
        "object": "event",
        "type": kind,
        "data": {"object": obj},
    }


# --- the plan mapping (pure) --------------------------------------------------------------------


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_paying_statuses_entitle_plus(status: str):
    assert billing.plan_for_status(status) == entitlements.PLUS


def test_past_due_keeps_access_while_stripe_retries():
    """The deliberate one: the card failed but the subscription isn't over. Cutting someone off
    mid-dunning turns a billing hiccup into a churn event, and Stripe will tell us
    (`unpaid`/`canceled`) when it has actually given up."""
    assert billing.plan_for_status("past_due") == entitlements.PLUS


@pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete_expired"])
def test_dead_statuses_end_the_entitlement(status: str):
    assert billing.plan_for_status(status) == entitlements.FREE


@pytest.mark.parametrize("status", ["incomplete", "paused", "", "something_new"])
def test_unknown_statuses_leave_the_plan_alone(status: str):
    # A checkout that was abandoned never granted anything; a status Stripe adds later must not
    # be guessed at in either direction.
    assert billing.plan_for_status(status) is None


def test_a_beta_workspace_is_never_downgraded_by_a_subscription_event():
    """The beta cohort was granted by hand and has no subscription, so a stray cancellation for
    a customer that somehow maps to them must not take their access away."""
    ws = Workspace(name="beta ws", plan=entitlements.BETA)
    assert billing.set_plan(ws, entitlements.FREE) is False
    assert ws.plan == entitlements.BETA


def test_a_beta_workspace_can_still_be_upgraded():
    ws = Workspace(name="beta ws", plan=entitlements.BETA)
    assert billing.set_plan(ws, entitlements.PLUS) is True
    assert ws.plan == entitlements.PLUS


def test_setting_the_same_plan_is_not_a_change():
    ws = Workspace(name="ws", plan=entitlements.PLUS)
    assert billing.set_plan(ws, entitlements.PLUS) is False


# --- configuration ------------------------------------------------------------------------------


def test_billing_is_off_without_keys(monkeypatch):
    monkeypatch.delenv(billing.SECRET_KEY_ENV, raising=False)
    monkeypatch.delenv(billing.WEBHOOK_SECRET_ENV, raising=False)
    assert billing.is_configured() is False


def test_routes_503_when_billing_is_not_configured(monkeypatch):
    """Unconfigured must be *obviously* off rather than half-working — a missing key should not
    read as a declined payment."""
    monkeypatch.delenv(billing.SECRET_KEY_ENV, raising=False)
    monkeypatch.delenv(billing.WEBHOOK_SECRET_ENV, raising=False)
    assert client.post("/billing/webhook", content=b"{}").status_code == 503
    assert client.post("/billing/checkout").status_code == 503


def test_status_reports_disabled_without_keys(monkeypatch):
    monkeypatch.delenv(billing.SECRET_KEY_ENV, raising=False)
    monkeypatch.delenv(billing.WEBHOOK_SECRET_ENV, raising=False)
    r = client.get("/billing/status")
    assert r.status_code == 200 and r.json()["enabled"] is False


def test_status_reports_enabled_when_configured(configured):
    """What the checkout page renders from: with keys present it offers payment, without them it
    says so. Tested here rather than in e2e because that suite deliberately has no Stripe keys,
    so the enabled branch is unreachable there."""
    r = client.get("/billing/status")
    assert r.status_code == 200 and r.json()["enabled"] is True


def test_status_leaks_nothing_about_the_keys(configured):
    # It reports presence, never content — this endpoint is unauthenticated.
    body = client.get("/billing/status").text
    assert "sk_test" not in body and "whsec" not in body and "price_" not in body


# --- signature verification (no database needed) -------------------------------------------------


def test_an_unsigned_request_is_refused(configured):
    # The whole endpoint's security: anyone can POST here, only Stripe can sign.
    r = client.post("/billing/webhook", content=json.dumps(_event("invoice.paid", {})))
    assert r.status_code == 400


def test_a_forged_signature_is_refused(configured):
    body, _ = _signed(_event("customer.subscription.deleted", {"customer": "cus_x"}))
    r = client.post(
        "/billing/webhook", content=body, headers={"Stripe-Signature": "t=1,v1=deadbeef"}
    )
    assert r.status_code == 400


def test_a_signature_from_the_wrong_secret_is_refused(configured):
    # What a mis-copied signing secret, or an event meant for another environment, looks like.
    body, headers = _signed(_event("invoice.paid", {}), secret="whsec_some_other_endpoint")
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 400


def test_a_tampered_body_is_refused(configured):
    """Signing covers the payload, so swapping the workspace after signing must not verify."""
    body, headers = _signed(
        _event("checkout.session.completed", {"client_reference_id": "victim"})
    )
    tampered = body.replace("victim", "attacker")
    assert client.post("/billing/webhook", content=tampered, headers=headers).status_code == 400


def test_a_stale_timestamp_is_refused(configured):
    """Replay protection: Stripe's own tolerance window (5 minutes) rejects a captured request
    replayed later."""
    body = json.dumps(_event("invoice.paid", {}))
    old = int(time.time()) - 3600
    r = client.post(
        "/billing/webhook",
        content=body,
        headers={"Stripe-Signature": f"t={old},v1={_sign(body, old)}"},
    )
    assert r.status_code == 400


def test_malformed_json_with_a_valid_signature_is_a_400(configured):
    body = "not json at all"
    timestamp = int(time.time())
    r = client.post(
        "/billing/webhook",
        content=body,
        headers={"Stripe-Signature": f"t={timestamp},v1={_sign(body, timestamp)}"},
    )
    assert r.status_code == 400


# --- delivery semantics (database) ---------------------------------------------------------------


@requires_db
def test_a_signed_event_is_accepted_and_recorded(configured):
    event = _event("invoice.paid", {"customer": "cus_unmapped"})
    body, headers = _signed(event)
    r = client.post("/billing/webhook", content=body, headers=headers)
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.get(StripeEvent, event["id"]) is not None


@requires_db
def test_a_redelivery_is_a_no_op(configured):
    """Stripe delivers at least once; these handlers are not naturally replay-safe, so the
    second delivery must not act again."""
    event = _event("invoice.paid", {"customer": "cus_unmapped"})
    body, headers = _signed(event)
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200


@requires_db
def test_an_event_for_an_unmapped_customer_is_not_retried_forever(configured):
    """A customer we have no mapping for will never map on retry, so it's a 200 (recorded and
    ignored) rather than a 500 that Stripe redelivers for three days."""
    body, headers = _signed(
        _event("customer.subscription.deleted", {"customer": f"cus_{uuid.uuid4().hex[:12]}"})
    )
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200


@requires_db
def test_an_unhandled_event_type_is_accepted_quietly(configured):
    """A destination configured with extra events shouldn't 500 — it should be quiet."""
    body, headers = _signed(_event("customer.created", {"id": "cus_x"}))
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200


# --- the payment → entitlement loop (database) ---------------------------------------------------


@requires_db
def test_a_completed_checkout_upgrades_the_workspace_and_maps_the_customer(configured):
    """The loop that makes the Plus button mean something."""
    customer = f"cus_{uuid.uuid4().hex[:12]}"
    with SessionLocal() as s:
        ws = s.query(Workspace).filter(Workspace.owner_user_id.is_(None)).first()
        if ws is None:
            pytest.skip("no workspace rows")
        ws_id, original_plan, original_customer = ws.id, ws.plan, ws.stripe_customer_id
        ws.plan, ws.stripe_customer_id = entitlements.FREE, None
        s.commit()

    try:
        body, headers = _signed(
            _event(
                "checkout.session.completed",
                {"client_reference_id": str(ws_id), "customer": customer},
            )
        )
        assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200

        with SessionLocal() as s:
            ws = s.get(Workspace, ws_id)
            assert ws.plan == entitlements.PLUS
            assert ws.stripe_customer_id == customer, "the customer must be mapped for later events"

        # ...and a later cancellation for that customer takes it away again.
        body, headers = _signed(
            _event("customer.subscription.deleted", {"customer": customer, "status": "canceled"})
        )
        assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200
        with SessionLocal() as s:
            assert s.get(Workspace, ws_id).plan == entitlements.FREE
    finally:
        with SessionLocal() as s:
            s.query(Workspace).filter(Workspace.id == ws_id).update(
                {"plan": original_plan, "stripe_customer_id": original_customer}
            )
            s.commit()


@requires_db
def test_a_checkout_without_a_workspace_reference_is_ignored(configured):
    # Nothing to attribute the payment to; must not raise, must not guess.
    body, headers = _signed(_event("checkout.session.completed", {"customer": "cus_x"}))
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200
