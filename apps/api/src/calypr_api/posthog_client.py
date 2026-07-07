"""Shared PostHog client instance for server-side analytics."""

from __future__ import annotations

import atexit

from posthog import Posthog

from calypr_api.config import settings

posthog_client = Posthog(
    settings.posthog_project_token or "placeholder",
    host=settings.posthog_host,
    enable_exception_autocapture=True,
    disabled=not bool(settings.posthog_project_token),
)

atexit.register(posthog_client.shutdown)
