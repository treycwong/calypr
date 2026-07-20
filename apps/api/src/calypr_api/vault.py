"""Envelope encryption for connector credentials — the one place secrets are protected at rest.

OAuth tokens and bearer secrets for MCP connectors are Fernet-encrypted before they touch the
`connector_credential` table and decrypted only server-side at run time. The master secret comes
from `CALYPR_VAULT_KEY`; any string works (it's hashed into a Fernet key), so operators can use a
passphrase. In dev/CI an insecure fixed key is used so tests and local dev stay key-free — but in
production a missing key is fail-closed (the vault refuses to encrypt/decrypt) so a real deployment
can never silently persist tokens under the throwaway dev key."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from calypr_api.config import settings

# Used only when CALYPR_VAULT_KEY is unset AND the environment is not production. Its whole point
# is to be well-known and worthless: it lets CI/local encrypt round-trip without a configured key.
_DEV_FALLBACK_SECRET = "calypr-dev-insecure-vault-key-do-not-use-in-prod"


class VaultUnavailable(RuntimeError):
    """Raised when the vault is asked to (de)crypt in production without a configured key."""


def _is_production_like() -> bool:
    """A positive signal that this is a real deployment, so the dev fallback key must NOT be
    used. `internal_key` is the shared secret the trusted Next proxy presents — it is only ever
    set in a real deployment, so its presence means production even if `CALYPR_ENVIRONMENT` was
    left unset. This closes the footgun where a misconfigured env silently encrypts every
    workspace secret under the public dev key."""
    return settings.environment == "production" or bool(settings.internal_key)


def _master_secret() -> str:
    if settings.vault_key:
        return settings.vault_key
    if _is_production_like():
        raise VaultUnavailable(
            "CALYPR_VAULT_KEY is required in production (or whenever CALYPR_INTERNAL_KEY is "
            "set) to store connector credentials — refusing the insecure dev fallback key."
        )
    return _DEV_FALLBACK_SECRET


def _fernet() -> Fernet:
    # Any master secret → a valid 32-byte url-safe base64 Fernet key via SHA-256.
    key = base64.urlsafe_b64encode(hashlib.sha256(_master_secret().encode()).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns url-safe base64 ciphertext (a Fernet token)."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored secret. Raises `VaultUnavailable` if the key can't open the token
    (rotated/absent key) so callers fail closed rather than leaking a partial credential."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise VaultUnavailable(
            "connector credential could not be decrypted — the vault key may have changed."
        ) from exc
