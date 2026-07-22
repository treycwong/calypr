"""The workspace's default model, and where it gets applied.

Node configs ship `model: ""` — inherit — so the model a canvas runs on is a preference chosen
once in Settings → Workspace rather than a field to set on every block. Resolution order, in
`calypr_nodes.effective_model`:

    the node's own model  →  workspace.default_model  →  PLATFORM_DEFAULT_MODEL (gpt-4o-mini)

The runtime resolves this itself (the id reaches `NodeContext.default_model`), so this module
exists for the *other* consumer: `/codegen`, which has no `NodeContext` and must emit a concrete
model into the generated file. Without it, generated code would fall back to the platform
default and silently disagree with what the same graph does when run.
"""

from __future__ import annotations

import logging
import uuid

from calypr_dsl import GraphSpec

from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal

log = logging.getLogger(__name__)

#: Node types whose `model` field is an LLM the workspace default applies to. Image and Voice
#: name their own models and resolve through separate factories, so they're deliberately absent.
LLM_NODE_TYPES = frozenset({"agent", "responder", "revisor", "evaluator", "memory", "router"})


def workspace_default_model(workspace_id: uuid.UUID | None) -> str:
    """The workspace's preferred model, or "" to mean the platform default.

    Best-effort: a missing workspace or an unavailable DB resolves to "", which every caller
    already treats as "use the platform default". A run must not fail over a preference."""
    if workspace_id is None:
        return ""
    try:
        with SessionLocal() as session:
            ws = session.get(Workspace, workspace_id)
            return ws.default_model if ws else ""
    except Exception:
        log.warning("default model lookup failed; using the platform default", exc_info=True)
        return ""


def strip_fake_models(spec: dict) -> tuple[dict, int]:
    """Rewrite `model: "fake"` → `""` (inherit) on LLM nodes of a stored graph.

    Repairs agents saved from the templates that shipped the test seam: their stored
    `graph_spec` keeps whatever model it was saved with, so changing the *defaults* doesn't help
    them — they'd go on answering "Echo: …" forever. Returns the (possibly new) spec and how
    many nodes changed, so the migration can report what it touched.

    Pure and dict-shaped rather than typed: a migration must be able to read rows written by
    older code without the current `GraphSpec` refusing them. Only `fake` is rewritten — an
    explicit real model is a choice, and Image/Voice nodes aren't in `LLM_NODE_TYPES` at all."""
    nodes = spec.get("nodes")
    if not isinstance(nodes, list):
        return spec, 0
    changed = 0
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") not in LLM_NODE_TYPES:
            continue
        config = node.get("config")
        if isinstance(config, dict) and config.get("model") == "fake":
            config["model"] = ""
            changed += 1
    return spec, changed


def apply_default_model(graph: GraphSpec, default_model: str) -> GraphSpec:
    """Fill in `model` on LLM nodes that don't name one, so codegen emits what a run would use.

    Returns the graph unchanged when there's no preference to apply — the platform default is
    the generator's own fallback, so writing it in here would only add noise to the diff.
    A node that *does* name a model is never touched: an explicit choice outranks the default.
    """
    if not default_model:
        return graph
    patched = graph.model_copy(deep=True)
    for node in patched.nodes:
        if node.type in LLM_NODE_TYPES and isinstance(node.config, dict):
            if not node.config.get("model"):
                node.config["model"] = default_model
    return patched
