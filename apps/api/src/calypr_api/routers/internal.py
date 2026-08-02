"""Scheduled maintenance, triggered over HTTP because there is no scheduler.

The API runs on Railway and the web app on Vercel, which already has cron. So these are plain
endpoints that a Vercel cron route calls with the internal key, rather than a second scheduler
to operate. They are **not** part of the public surface (`include_in_schema=False`) and refuse
to run at all without a key configured — an unauthenticated GC endpoint is a delete button on
the internet.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from calypr_api import storage_usage
from calypr_api.config import settings
from calypr_api.db.session import SessionLocal

log = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", include_in_schema=False)


def _require_internal_key(request: Request) -> None:
    """Fails **closed**, including when no key is configured.

    The opposite of every other gate in this codebase, and deliberately so: elsewhere a missing
    key means local dev and the carve-out is to *allow*. Here the operation deletes data, so an
    unconfigured deployment must not expose it."""
    if not settings.internal_key:
        raise HTTPException(status_code=503, detail="internal endpoints are not configured")
    if request.headers.get("x-calypr-internal-key") != settings.internal_key:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/gc/measure-storage")
def measure_storage(request: Request) -> dict[str, int]:
    """Refresh every account's `storage_bytes`. Nightly; see `storage_usage` for what it counts."""
    _require_internal_key(request)
    with SessionLocal() as session:
        measured = storage_usage.measure_all(session)
    log.info("storage measured for %d accounts", measured)
    return {"accounts": measured}


@router.post("/gc/checkpoints")
def gc_checkpoints(request: Request) -> dict[str, int]:
    """Delete run state past its plan's retention window — the thing that bounds storage."""
    _require_internal_key(request)
    with SessionLocal() as session:
        result = storage_usage.gc_checkpoints(session)
    log.info("checkpoint gc: %s threads, %s rows", result["threads"], result["rows"])
    return result
