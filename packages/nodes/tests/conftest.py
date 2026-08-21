"""Keep the node suite off the developer's real blob store.

`calypr_api.config` calls `load_dotenv` on the repo-root `.env` at import time, and pytest collects
the whole repo in one process — so the moment any module imports the API config, everything a
developer keeps in `.env` is also set for these tests. That is harmless for most settings and
actively wrong for this one.

`store_asset` reads `BLOB_READ_WRITE_TOKEN` from the environment. With a real token present, every
Image/Voice/3D node test stops exercising the `data:` fallback it asserts on **and starts uploading
real files to a live Vercel Blob store** — a paid side effect of running the tests, and orphaned
objects nothing will ever clean up. It also makes the suite's result depend on whether the
developer happens to have configured blob storage: these very tests passed alone and failed in the
full run, which is the confusing half of the bug.

A test that wants the durable path monkeypatches `put_blob` (see `test_mesh_node.py`), which is the
honest way to exercise it — no network either way. Mirrors `apps/api/tests/conftest.py`'s
`_unmetered_by_default` for the same reason.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_blob_store(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
