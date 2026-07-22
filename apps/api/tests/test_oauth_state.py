"""OAuth `state` — the CSRF guard on the Tier A (Notion) connect flow.

The attack it stops: an attacker sends a victim to our callback URL carrying the attacker's
authorization code, and the victim's workspace silently ends up wired to the attacker's Notion
account. Every test below is one way that forgery must fail.
"""

from __future__ import annotations

import time
import uuid

import pytest
from calypr_api import oauth_state
from calypr_api.oauth_state import OAuthStateError

WS = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_WS = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True)
def _signing_secret(monkeypatch):
    """Pin a signing secret so the test doesn't depend on the developer's .env."""
    monkeypatch.setattr(oauth_state.settings, "vault_key", "test-signing-secret")


def test_round_trip():
    oauth_state.verify(oauth_state.issue(WS), WS)  # does not raise


def test_tokens_are_unguessable_and_unique():
    a, b = oauth_state.issue(WS), oauth_state.issue(WS)
    assert a != b  # nonce, so a leaked token can't be predicted from another


def test_missing_state_is_rejected():
    with pytest.raises(OAuthStateError):
        oauth_state.verify("", WS)


@pytest.mark.parametrize(
    "state",
    ["garbage", "no-dot-separator", "a.b", "!!!.???"],
    ids=["garbage", "no-sep", "bad-b64", "non-b64"],
)
def test_malformed_state_is_rejected(state: str):
    with pytest.raises(OAuthStateError):
        oauth_state.verify(state, WS)


def test_tampered_payload_is_rejected():
    """The forgery that matters: swap the workspace in the payload and keep the signature."""
    good = oauth_state.issue(WS)
    encoded, sig = good.split(".", 1)
    payload = oauth_state._unb64(encoded).decode()
    forged = payload.replace(str(WS), str(OTHER_WS))
    with pytest.raises(OAuthStateError):
        oauth_state.verify(f"{oauth_state._b64(forged.encode())}.{sig}", OTHER_WS)


def test_state_signed_with_another_secret_is_rejected(monkeypatch):
    stolen = oauth_state.issue(WS)
    monkeypatch.setattr(oauth_state.settings, "vault_key", "a-different-secret")
    with pytest.raises(OAuthStateError):
        oauth_state.verify(stolen, WS)


def test_state_from_another_workspace_is_rejected():
    """A *validly signed* token still must not be replayed into someone else's workspace."""
    with pytest.raises(OAuthStateError):
        oauth_state.verify(oauth_state.issue(WS), OTHER_WS)


def test_expired_state_is_rejected(monkeypatch):
    state = oauth_state.issue(WS)
    later = time.time() + oauth_state.STATE_TTL_SECONDS + 1  # captured before patching
    monkeypatch.setattr(oauth_state.time, "time", lambda: later)
    with pytest.raises(OAuthStateError):
        oauth_state.verify(state, WS)


def test_falls_back_to_the_client_secret_when_no_vault_key(monkeypatch):
    """The connect/callback routes 501 without a Notion client secret, so this is always
    available even on a deployment that hasn't set a vault key."""
    monkeypatch.setattr(oauth_state.settings, "vault_key", "")
    monkeypatch.setattr(oauth_state.settings, "notion_client_secret", "notion-secret")
    oauth_state.verify(oauth_state.issue(WS), WS)


def test_no_secret_at_all_refuses_to_issue(monkeypatch):
    monkeypatch.setattr(oauth_state.settings, "vault_key", "")
    monkeypatch.setattr(oauth_state.settings, "notion_client_secret", "")
    with pytest.raises(OAuthStateError):
        oauth_state.issue(WS)
