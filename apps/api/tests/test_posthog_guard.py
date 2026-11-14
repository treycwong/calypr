"""Only a production process sends to PostHog (CAL-36).

The repo-root `.env` holds the production project token and every local process loads it, so this
suite used to send its fixtures to production as real events, including fake payments.
"""

from __future__ import annotations

from calypr_api.posthog_client import analytics_enabled, posthog_client


def test_production_with_a_token_sends():
    assert analytics_enabled("production", "phc_real") is True


def test_a_token_outside_production_does_not_send():
    for env in ("development", "test", "staging", ""):
        assert analytics_enabled(env, "phc_real") is False


def test_no_token_never_sends():
    assert analytics_enabled("production", "") is False


def test_this_test_process_is_not_sending():
    """The guard as wired, not just the function: this suite runs with whatever token a
    developer's `.env` holds, and must still never report."""
    assert posthog_client.disabled is True
