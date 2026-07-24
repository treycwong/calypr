"""May this workspace run *this graph* on the platform's keys?

One question decides it: **does anything here run on our keys at all?** If nothing does — every
LLM node is covered by a key the workspace stored — the run costs us nothing and is always
allowed, whatever the balance says. Only when some node would land on our keys does the credit
balance matter, and that question belongs to `credits.check_can_run`.

Both plans work the same way: spend the monthly grant on platform models, and when it runs out
either bring your own key or wait for the reset. Nothing here gates on the plan. An earlier
version refused Free any platform run at all (BYO-key only, per an older reading of
`PRICING-SPEC` §1); that was reversed before it ever shipped, because it made a new Free user's
very first Run an error message.

Graph-shaped, so it can't be a FastAPI dependency — the graph arrives in the request body.
Callers run it off the event loop (it touches the DB) and stream the `(code, message)` back
in-band, the same way `check_can_run`'s result was delivered before.
"""

from __future__ import annotations

import logging
import uuid

from calypr_dsl import GraphSpec

from calypr_api import credits
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal
from calypr_api.model_access import platform_key_models, runs_on_own_key
from calypr_api.provider_keys import byok_providers

log = logging.getLogger(__name__)


def check_run_gates(workspace_id: uuid.UUID | None, graph: GraphSpec) -> tuple[str, str] | None:
    """`(code, message)` explaining why this graph may not run, or None if it may.

    The short-circuit is the point. Asking the balance about a run we don't pay for is how a
    customer who had done exactly what we asked — brought their own key — still got refused for
    having no credits, and how "add your own API key to keep running" became advice that didn't
    work. A run on their own keys is always allowed.

    Carve-outs are deliberately identical to `credits.check_can_run` — enforced only on a real
    deployment (`CALYPR_INTERNAL_KEY`), never for the shared dev workspace — so the two can never
    disagree about who is being metered. Local dev, CI and the e2e suite keep working unmetered,
    and anonymous production traffic stays the spend cap's problem rather than becoming the first
    visitor's.

    **Fails open**, for the same reason as the credit check: a DB hiccup must not stop people
    working, and the loss is bounded by one run plus `CALYPR_PLATFORM_SPEND_CAP_USD`.
    """
    if workspace_id is None or not settings.internal_key:
        return None
    if str(workspace_id) == DEV_WORKSPACE_ID:
        return None
    try:
        with SessionLocal() as session:
            workspace = session.get(Workspace, workspace_id)
            if workspace is None:
                return None
            on_platform = platform_key_models(
                graph, byok_providers(workspace_id), workspace.default_model or ""
            )
            if not on_platform:
                return None  # every node runs on their own key — nothing of ours is being spent
    except Exception:
        log.warning("run access check failed — allowing the run", exc_info=True)
        return None

    # Something in this graph lands on our keys, so the balance is now the question. Delegated
    # rather than reimplemented: `check_can_run` owns grant-then-check, and two copies of that
    # would eventually disagree about when a lazy grant is issued.
    if message := credits.check_can_run(workspace_id):
        return (credits.INSUFFICIENT_CREDITS, message)
    return None


def assist_on_own_key(workspace_id: uuid.UUID | None, model_id: str) -> bool:
    """Whether the assistant will draft on the workspace's own key, so its balance is irrelevant.

    The `/assist` counterpart of the `not on_platform` short-circuit above: the assistant is a
    single model call rather than a graph, so the same question needs only its resolved id."""
    if workspace_id is None:
        return False
    return runs_on_own_key(model_id, byok_providers(workspace_id))
