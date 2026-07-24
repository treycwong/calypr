"""May this workspace run *this graph*, and on whose keys?

The pre-run gate. It answers two refusals — Free's BYO-key-only rule
(`entitlements.requires_own_key`) and the credit balance (`credits.check_can_run`) — behind one
question asked first: **does anything in this graph run on our keys at all?**

They are one function rather than two because that shared premise is what makes them correct.
Asked separately, the balance check refuses a run that costs us nothing, which is how a Plus
customer with their own key and a spent balance got locked out of a call we never pay for, and how
a Free workspace got told to add a key it had already added. Neither refusal collects any money in
that case; both just block someone who has done exactly what we asked.

Graph-shaped, so it can't be a FastAPI dependency — the graph arrives in the request body. Callers
run it off the event loop (it touches the DB) and stream the `(code, message)` back in-band, the
same way `check_can_run`'s result was delivered before.
"""

from __future__ import annotations

import logging
import uuid

from calypr_dsl import GraphSpec

from calypr_api import credits, entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal
from calypr_api.model_access import platform_key_models, provider_label, runs_on_own_key
from calypr_api.provider_keys import byok_providers

log = logging.getLogger(__name__)

#: Stable machine hint for the client, matching `credits.INSUFFICIENT_CREDITS`'s role. The web app
#: switches on the code to offer "Add a key" / "Upgrade" rather than parsing prose.
OWN_KEY_REQUIRED = "own_key_required"


def check_run_gates(workspace_id: uuid.UUID | None, graph: GraphSpec) -> tuple[str, str] | None:
    """`(code, message)` explaining why this graph may not run, or None if it may.

    **One gate, not two, because both questions share a premise: does anything here run on
    *our* keys?** If nothing does, neither the plan rule nor the credit balance is relevant —
    the run is free to us, so refusing it collects no money and only blocks someone who has
    already done what we asked. That is the case this function exists to let through:

    - Free is BYO-key only, so a Free workspace with keys for every model in the graph runs fine
      even on a zero balance — its credits are an assistant budget it may well have spent.
    - A Plus workspace out of credits keeps working on its own keys instead of being told to wait
      for a reset that would change nothing about a call we never pay for.

    Only when some node *would* land on our keys do the two refusals apply, in that order: the
    plan rule first (Free may not spend our keys at all, and "add a key or upgrade" is the
    actionable answer), then the balance.

    Carve-outs are deliberately identical to `credits.check_can_run` — enforced only on a real
    deployment (`CALYPR_INTERNAL_KEY`), never for the shared dev workspace — so the gates can
    never disagree about who is being metered. Local dev, CI and the e2e suite keep working
    unmetered, and anonymous production traffic stays the spend cap's problem rather than
    becoming the first visitor's.

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
            if entitlements.requires_own_key(workspace.plan):
                return (OWN_KEY_REQUIRED, _message(on_platform))
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


def _message(models: list[str]) -> str:
    """What a Free user is told, phrased as the two things they can actually do about it.

    Names the providers rather than the model ids: "add an OpenAI key" is an instruction, whereas
    "gpt-4o-mini needs a key" leaves them to work out where that key comes from."""
    from calypr_model import provider_of  # local: keeps the model factory off this import path

    providers = sorted({provider_of(m) for m in models})
    labels = [provider_label(p) for p in providers]
    if len(labels) == 1:
        which = f"an {labels[0]}" if labels[0][0] in "AEIOU" else f"a {labels[0]}"
        need = f"{which} API key"
    else:
        need = f"API keys for {', '.join(labels[:-1])} and {labels[-1]}"
    return (
        f"The Free plan runs on your own keys. Add {need} in Settings → API Keys to run this "
        "agent for free, or upgrade to Plus to run it on ours."
    )
