"""Platform-wide spend kill-switch (PRICING-SPEC §9, WEEK2 plan §C4).

A pre-billing loss firewall: if this month's total recorded `run.cost_usd` reaches
`CALYPR_PLATFORM_SPEND_CAP_USD`, new runs/assists are refused before they start. Disabled
when the cap is unset/0.

The check is on the hot path, so the month-to-date sum is cached in-process for 60s — at most
one cheap aggregate query per minute. If the DB is unreachable the switch **fails open**
(availability over enforcement, pre-billing): we'd rather serve than block on a metering query.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import text

from calypr_api.config import settings
from calypr_api.db.session import SessionLocal

log = logging.getLogger("calypr_api")

_CACHE_TTL_SECONDS = 60.0
# (monotonic timestamp, month-to-date USD). None until the first successful query.
_cached: tuple[float, float] | None = None


def _month_to_date_spend() -> float:
    """Sum of this month's recorded run cost, across all workspaces (platform-wide)."""
    with SessionLocal() as session:
        value = session.execute(
            text(
                "SELECT coalesce(sum(cost_usd), 0) FROM run "
                "WHERE created_at >= date_trunc('month', now())"
            )
        ).scalar()
        return float(value or 0)


def reset_cache() -> None:
    """Drop the cached spend (tests; a manual cap change that must take effect immediately)."""
    global _cached
    _cached = None


def over_spend_cap() -> bool:
    """True iff the platform cap is enabled and this month's spend has reached it.

    Cached for 60s. DB errors fail open (return False)."""
    cap = settings.platform_spend_cap_usd
    if not cap or cap <= 0:
        return False

    global _cached
    now = time.monotonic()
    if _cached is None or now - _cached[0] >= _CACHE_TTL_SECONDS:
        try:
            spend = _month_to_date_spend()
        except Exception:
            log.warning("spend cap check failed — failing open", exc_info=True)
            return False
        _cached = (now, spend)
    return _cached[1] >= cap
