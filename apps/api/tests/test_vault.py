"""The credential vault: Fernet envelope encryption with a dev fallback + prod fail-closed.

DB-free — pure crypto + config behavior, so it runs everywhere."""

from __future__ import annotations

import pytest
from calypr_api import vault
from calypr_api.config import settings


def test_round_trip_and_ciphertext_differs():
    token = "ntn_super_secret_value"
    ciphertext = vault.encrypt(token)
    assert ciphertext != token  # actually encrypted, not stored in the clear
    assert vault.decrypt(ciphertext) == token


def test_decrypt_rejects_a_tampered_or_foreign_token():
    with pytest.raises(vault.VaultUnavailable):
        vault.decrypt("not-a-valid-fernet-token")


def test_production_without_a_key_is_fail_closed(monkeypatch):
    # In prod a missing CALYPR_VAULT_KEY must refuse to (de)crypt rather than silently using the
    # throwaway dev key — otherwise real tokens would be stored under a well-known key.
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "vault_key", "")
    with pytest.raises(vault.VaultUnavailable):
        vault.encrypt("x")


def test_configured_key_round_trips_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "vault_key", "a-real-operator-passphrase")
    assert vault.decrypt(vault.encrypt("secret")) == "secret"


def test_internal_key_set_forces_fail_closed_without_vault_key(monkeypatch):
    # The trusted-proxy secret is only ever set in a real deployment; its presence must forbid
    # the dev fallback even if CALYPR_ENVIRONMENT was left unset (the misconfiguration footgun).
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "vault_key", "")
    monkeypatch.setattr(settings, "internal_key", "proxy-shared-secret")
    with pytest.raises(vault.VaultUnavailable):
        vault.encrypt("x")
