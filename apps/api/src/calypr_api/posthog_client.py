"""Shared PostHog client instance for server-side analytics."""

from __future__ import annotations

import atexit
import logging

from posthog import Posthog

from calypr_api.config import settings


def analytics_enabled(environment: str, token: str) -> bool:
    """Whether server-side events may be sent: a token **and** a production process.

    The repo-root `.env` carries the production project token, and `config.py` loads that file
    for every local process, the test suite included. So until this check, `pytest` and local dev
    sent their fixtures to the production project as real events: fake `subscription_activated`
    payments, runs for `dev-user` and an `attacker-…` fixture, shares on the dev workspace
    (CAL-36). It's the same trap the blob guard closes (`config.guard_prod_blob_store`), and it is
    closed the same way: production is the only environment that reports. Railway sets
    `CALYPR_ENVIRONMENT=production`; nothing else does."""
    return bool(token) and environment == "production"


_enabled = analytics_enabled(settings.environment, settings.posthog_project_token)
if settings.posthog_project_token and not _enabled:
    logging.getLogger(__name__).info(
        "PostHog token present but CALYPR_ENVIRONMENT is %r, so analytics are off.",
        settings.environment,
    )

posthog_client = Posthog(
    settings.posthog_project_token or "placeholder",
    host=settings.posthog_host,
    # Exception autocapture is part of the same pipe: local tracebacks don't belong in production.
    enable_exception_autocapture=_enabled,
    disabled=not _enabled,
)

atexit.register(posthog_client.shutdown)
