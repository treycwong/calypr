"""The guard that keeps local dev out of the production blob store.

Six weeks of local test media went into `calypr-media` because the repo-root `.env` held its
token. That exhausted the Hobby quota and suspended 3D and Video in production. These tests pin
the guard that drops that token anywhere except production.
"""

from __future__ import annotations

from calypr_api.config import PROD_BLOB_STORE_ID, guard_prod_blob_store, settings

PROD_TOKEN = f"vercel_blob_rw_{PROD_BLOB_STORE_ID}_secretpart"
DEV_TOKEN = "vercel_blob_rw_someDevStoreId123_secretpart"


def test_a_production_token_is_dropped_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    env = {"BLOB_READ_WRITE_TOKEN": PROD_TOKEN}
    assert guard_prod_blob_store(env) is True
    assert "BLOB_READ_WRITE_TOKEN" not in env


def test_production_keeps_its_own_token(monkeypatch):
    """The guard must never fire in production, or media stops working there."""
    monkeypatch.setattr(settings, "environment", "production")
    env = {"BLOB_READ_WRITE_TOKEN": PROD_TOKEN}
    assert guard_prod_blob_store(env) is False
    assert env["BLOB_READ_WRITE_TOKEN"] == PROD_TOKEN


def test_a_dev_store_token_is_left_alone(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    env = {"BLOB_READ_WRITE_TOKEN": DEV_TOKEN}
    assert guard_prod_blob_store(env) is False
    assert env["BLOB_READ_WRITE_TOKEN"] == DEV_TOKEN


def test_no_token_is_fine(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    assert guard_prod_blob_store({}) is False
