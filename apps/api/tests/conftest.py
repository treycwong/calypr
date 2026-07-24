"""Shared test setup: keep the suite independent of the developer's `.env`.

`config.py` calls `load_dotenv` on the repo-root `.env`, so anything a developer sets there is
also set while the tests run. That is fine for most settings and actively wrong for one.
"""

from __future__ import annotations

import pytest
from calypr_api.config import settings


@pytest.fixture(autouse=True)
def _unmetered_by_default(monkeypatch):
    """Force `internal_key` empty unless a test opts in.

    `CALYPR_INTERNAL_KEY` is the switch that turns on tenant scoping and the billing gates
    (`credits.check_can_run`, `run_access.check_run_gates`, `deps.require_code_export`). The
    suite is written for it being unset — the same carve-out that keeps CI and `start.sh`
    working without keys or a database.

    Setting it locally to exercise the paid tiers therefore broke 33 tests that had nothing to
    do with billing: requests started 401ing for want of a proxy header no test sends. The suite
    should not depend on whether a developer happens to be testing enforcement that day, so the
    default is pinned here and the tests that *want* enforcement set it themselves with
    `monkeypatch.setattr(settings, "internal_key", "prod-key")` — an explicit opt-in that reads
    as part of the test rather than as ambient state.
    """
    monkeypatch.setattr(settings, "internal_key", "")
