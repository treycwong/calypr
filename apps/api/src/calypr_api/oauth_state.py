"""OAuth `state` — CSRF protection for the Tier A connect flow (PRODUCTION.md pre-Notion fix).

Without a `state`, anyone can send a victim to our callback URL carrying *their* authorization
code, and the victim's workspace silently ends up connected to the attacker's Notion account
(or vice versa). The fix is the standard one: mint an unguessable value when the consent flow
starts, hand it to the provider, and refuse any callback that doesn't hand it back.

The token is a signed, expiring blob rather than a stored row: it carries the workspace it was
issued for, so verification is a signature check plus a comparison against the caller's own
workspace — no shared session store, correct across replicas, and nothing to clean up.

Not a nonce store: a stolen token stays usable inside its short TTL. That is the same posture
as a signed-cookie state and is proportional here; a single-use table can come later if the
connector set grows.
"""

from __future__ import annotations

import base64
import hmac
import secrets
import time
import uuid
from hashlib import sha256

from calypr_api.config import settings

#: How long a consent flow may stay open. Long enough to read Notion's consent screen and pick a
#: workspace, short enough that a leaked URL goes stale quickly.
STATE_TTL_SECONDS = 600


class OAuthStateError(RuntimeError):
    """The state is missing, malformed, tampered with, expired, or for another workspace."""


def _signing_key() -> bytes:
    """The HMAC key. Prefers the vault master secret; falls back to the OAuth client secret,
    which the connect/callback routes have already proven non-empty (they 501 without it). Both
    are server-side-only secrets, so either yields an unforgeable state."""
    material = settings.vault_key or settings.notion_client_secret
    if not material:
        raise OAuthStateError("no signing secret configured")
    return sha256(material.encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(workspace_id: uuid.UUID) -> str:
    """Mint a state token binding this consent flow to `workspace_id`."""
    payload = f"{workspace_id}:{int(time.time())}:{secrets.token_urlsafe(16)}".encode()
    sig = hmac.new(_signing_key(), payload, sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify(state: str, workspace_id: uuid.UUID) -> None:
    """Raise `OAuthStateError` unless `state` is one we issued, recently, for this workspace."""
    if not state:
        raise OAuthStateError("missing state")
    try:
        encoded, sig = state.split(".", 1)
        payload = _unb64(encoded)
        expected = hmac.new(_signing_key(), payload, sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig)):
            raise OAuthStateError("bad signature")
        issued_for, issued_at, _nonce = payload.decode().split(":", 2)
    except OAuthStateError:
        raise
    except Exception as exc:  # malformed base64 / missing separator / bad utf-8
        raise OAuthStateError("malformed state") from exc

    if time.time() - int(issued_at) > STATE_TTL_SECONDS:
        raise OAuthStateError("state expired")
    # The signature proves *we* minted it; this proves it was minted for *this* caller — which
    # is what stops a valid token from one workspace being replayed into another.
    if issued_for != str(workspace_id):
        raise OAuthStateError("state was issued for another workspace")
