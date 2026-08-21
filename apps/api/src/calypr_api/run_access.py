"""May this workspace run *this graph* on the platform's keys?

One question decides it: **does anything here run on our keys at all?** If nothing does — every
LLM node is covered by a key the workspace stored — the run costs us nothing and is always
allowed, whatever the balance says. Only when some node would land on our keys does the credit
balance matter, and that question belongs to `credits.check_can_run`.

Both plans work the same way: spend the monthly grant on platform models, and when it runs out
either bring your own key or wait for the reset. **The plan never decides which *models* you may
run.** An earlier version refused Free any platform run at all (BYO-key only, per an older
reading of `PRICING-SPEC` §1); that was reversed before it ever shipped, because it made a new
Free user's very first Run an error message.

It does decide which **blocks** you may run, which is a different question. The generative media
blocks (`entitlements.PLUS_NODE_TYPES`) cost real money per output rather than per token, so they
are a paid entitlement — and unlike the credit gate, a BYO key does not open them. That check runs
before the own-key short-circuit for exactly that reason.

And it decides *where* you may run, checked first of all: a workspace beyond the plan's cap
after a downgrade is read-only, so no run starts in it at all (`locking.py`). That gate is about
capacity the account no longer has — and like the block gate, waiting for the monthly reset does
nothing for it.

Graph-shaped, so it can't be a FastAPI dependency — the graph arrives in the request body.
Callers run it off the event loop (it touches the DB) and stream the `(code, message)` back
in-band, the same way `check_can_run`'s result was delivered before.
"""

from __future__ import annotations

import logging
import uuid

from calypr_dsl import GraphSpec
from sqlalchemy import text

from calypr_api import credits, entitlements, locking
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal
from calypr_api.errors import PLAN_REQUIRED, WORKSPACE_LOCKED
from calypr_api.model_access import platform_key_models, runs_on_own_key
from calypr_api.provider_keys import byok_providers

log = logging.getLogger(__name__)

#: A workspace's plan lives on its account (migration 0016). Same join `deps` uses; duplicated as
#: a constant rather than imported because `deps` is the FastAPI dependency layer and this module
#: is deliberately graph-shaped and framework-free.
_PLAN_FOR_WORKSPACE = (
    "SELECT a.plan FROM billing_account a JOIN workspace w ON w.account_id = a.id WHERE w.id = :id"
)

#: Palette labels for the gated block types, so the refusal names what the user actually dragged
#: onto the canvas rather than an internal node type.
_BLOCK_LABELS = {"mesh": "3D"}


def _plan_required_message(types: list[str]) -> str:
    """Copy for a graph containing blocks this plan doesn't include."""
    names = ", ".join(_BLOCK_LABELS.get(t, t) for t in types)
    plural = "blocks are" if len(types) > 1 else "block is"
    return f"The {names} {plural} part of Calypr Plus. Upgrade to run this agent."


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

    # Capacity before credits. A workspace the plan no longer covers is read-only, and saying
    # "you're out of credits" to someone whose real problem is a lapsed subscription sends them
    # to wait for a monthly reset that will not help.
    if locked := locking.locked_run_message(workspace_id):
        return (WORKSPACE_LOCKED, locked)

    try:
        with SessionLocal() as session:
            workspace = session.get(Workspace, workspace_id)
            if workspace is None:
                return None
            # Entitlement before cost. A paid block is refused whatever the balance says and
            # whoever's key would pay for it, so this sits above the own-key short-circuit.
            #
            # Inside the fail-open `try` with everything else, deliberately: a DB hiccup letting a
            # Free run through costs cents and is still backstopped by the spend cap, whereas
            # failing closed here would refuse *every* run whenever Postgres blinks.
            plan = session.execute(
                text(_PLAN_FOR_WORKSPACE), {"id": str(workspace_id)}
            ).scalar_one_or_none()
            if gated := entitlements.gated_nodes_in(graph, plan):
                return (PLAN_REQUIRED, _plan_required_message(gated))
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
