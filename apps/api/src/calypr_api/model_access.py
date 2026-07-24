"""Frontier models are BYO-key only — they are not part of the metered pricing model.

A *frontier* model is one we deliberately refuse to serve on the platform's own API key: the
workspace must store its own provider key (Settings → API Keys) and pays the provider directly.
Two consequences follow, and both are enforced here rather than trusted to the UI:

1. A run naming a frontier model with no key on file **degrades to `FALLBACK_MODEL`** and says
   so via a `notice` event. The frontier model itself is never served on the platform key, and
   the notice is not optional — see `substitute_missing_frontier_models`.
2. Its usage contributes **$0** to `run.cost_usd`, which is the platform-COGS figure the spend
   kill-switch sums (`spend.py`). Billing a BYO-key run to the platform would let one heavy user
   trip the month's kill-switch for everybody.

Keep this list short and deliberate. Everything absent from it is served on the platform key and
is metered normally.
"""

from __future__ import annotations

from calypr_dsl import GraphSpec
from calypr_model import provider_of

# Model-id prefix → the provider key a workspace must supply to use it. Prefix-matched (like
# `pricing.MODEL_PRICES`) so dated/suffixed ids — "kimi-k3-0711-preview" — are covered too.
FRONTIER_MODELS: dict[str, str] = {
    "kimi-k3": "moonshot",
    # No gpt-5.6 tier is offered in the pickers today (Terra was pulled). The entry stays as a
    # guard: the family is expensive and reasoning-heavy, so an id arriving via the API or an
    # imported graph must still be gated rather than quietly billed to the platform key.
    "gpt-5.6": "openai",
    "claude-opus-4-8": "anthropic",
}


def frontier_provider(model_id: str) -> str | None:
    """The provider whose BYO key `model_id` requires, or None if it isn't a frontier model."""
    m = model_id.lower().strip()
    for prefix, provider in FRONTIER_MODELS.items():
        if m.startswith(prefix):
            return provider
    return None


def is_frontier(model_id: str) -> bool:
    return frontier_provider(model_id) is not None


def missing_frontier_keys(graph: GraphSpec, keys: dict[str, str] | None) -> list[tuple[str, str]]:
    """Every (model_id, provider) in `graph` that needs a BYO key the workspace hasn't stored.

    Empty list ⇒ the run may proceed. Deduplicated and ordered so the error message is stable.
    """
    on_file = set(keys or {})
    missing: list[tuple[str, str]] = []
    for node in graph.nodes:
        model = node.config.get("model")
        if not isinstance(model, str):
            continue
        provider = frontier_provider(model)
        if provider is not None and provider not in on_file:
            pair = (model, provider)
            if pair not in missing:
                missing.append(pair)
    return missing


def runs_on_own_key(model_id: str, providers: set[str] | None) -> bool:
    """Whether `model_id` will run on the *workspace's* key rather than the platform's.

    This is the billing question, and it has exactly one correct answer: `factory._key` prefers a
    stored key over the server env for that provider, so "the workspace has a key for this
    model's provider" *is* "this call is billed to them, not us".

    Not to be confused with `is_frontier`, which asks whether a model is BYO-key **only**. Every
    frontier model runs on an own key, but the reverse doesn't hold — a workspace with an OpenAI
    key runs ordinary `gpt-4o-mini` traffic on it too, and charging credits for that would bill
    them twice for one call."""
    if not providers:
        return False
    return provider_of(model_id) in providers


def platform_key_models(
    graph: GraphSpec, providers: set[str] | None, default_model: str = ""
) -> list[str]:
    """Every distinct LLM model in `graph` that would run on the **platform's** key.

    Empty ⇒ the whole graph runs on the workspace's own keys. Used to enforce Free's BYO-key-only
    rule (`PRICING-SPEC` §1), so it resolves the same fallback chain the runtime does —
    `calypr_nodes.effective_model`: the node's own model → the workspace default → the platform
    default. Resolving it here rather than reading `config["model"]` raw is the difference between
    gating what actually runs and gating only the nodes that happened to name a model; a canvas of
    untouched nodes ships `model: ""` and would otherwise sail straight through the gate.
    """
    # Local imports: `registry` pulls the node runtime and `workspace_model` the DB session —
    # neither belongs in this module's import graph, which `pricing` imports lazily for the same
    # reason.
    from calypr_nodes.registry import PLATFORM_DEFAULT_MODEL

    from calypr_api.workspace_model import LLM_NODE_TYPES

    on_platform: list[str] = []
    for node in graph.nodes:
        if node.type not in LLM_NODE_TYPES or not isinstance(node.config, dict):
            continue
        configured = node.config.get("model")
        model = (configured if isinstance(configured, str) else "") or default_model
        model = model or PLATFORM_DEFAULT_MODEL
        if not runs_on_own_key(model, providers) and model not in on_platform:
            on_platform.append(model)
    return on_platform


#: Display names for the error copy. `.title()` would render "Openai" and "Moonshot (kimi)".
_PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "moonshot": "Moonshot",
    "google": "Google",
}


def provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, provider.title())


#: What a frontier model degrades to when the workspace has no key for it. Must be a
#: platform-served, cheap, non-frontier model — it runs on our key and is metered normally.
FALLBACK_MODEL = "gpt-4o-mini"


def substitute_missing_frontier_models(
    graph: GraphSpec, keys: dict[str, str] | None
) -> tuple[GraphSpec, list[tuple[str, str]]]:
    """Swap unkeyed frontier models for `FALLBACK_MODEL`, returning the rewritten graph and the
    (original_model, provider) pairs that were substituted.

    A run always produces output rather than dead-ending on a missing key — but the caller MUST
    surface the returned substitutions to the user. A silent swap would mean someone selects
    Opus 4.8, receives gpt-4o-mini output, and exports a graph that behaves unlike the one they
    just tested. Empty list ⇒ nothing changed and `graph` is returned untouched.
    """
    substituted = missing_frontier_keys(graph, keys)
    if not substituted:
        return graph, []
    swapped = graph.model_copy(deep=True)
    for node in swapped.nodes:
        model = node.config.get("model")
        if isinstance(model, str) and frontier_provider(model) is not None:
            if frontier_provider(model) not in set(keys or {}):
                node.config["model"] = FALLBACK_MODEL
    return swapped, substituted


def frontier_substitution_notice(substituted: list[tuple[str, str]]) -> str:
    """User-facing copy for a substituted run. Names what was swapped and how to get the real
    thing — this is the message that keeps the fallback from being a silent downgrade."""
    models = ", ".join(sorted({m for m, _ in substituted}))
    providers = ", ".join(sorted({provider_label(p) for _, p in substituted}))
    return (
        f"Ran on {FALLBACK_MODEL} instead of {models}, which needs your own API key. "
        f"Add your {providers} key in Settings → Workspace to use it."
    )


def frontier_key_error(missing: list[tuple[str, str]]) -> str:
    """User-facing copy for a refused run. Names the model and where to fix it — no key values."""
    models = ", ".join(sorted({m for m, _ in missing}))
    providers = ", ".join(sorted({provider_label(p) for _, p in missing}))
    # "your <Provider> key", not "a <Provider> key" — sidesteps a/an agreement across providers
    # ("a Anthropic key") and reads correctly however many providers are listed.
    return (
        f"{models} needs your own API key. Add your {providers} key in "
        "Settings → Workspace, then run again."
    )


def byo_providers_in_play(graph: GraphSpec, keys: dict[str, str] | None) -> set[str]:
    """Providers whose *workspace-stored* key this graph would actually use.

    Used to name the culprit when a provider rejects our credentials: if exactly one BYO key is
    in play, the rejection is unambiguously that one. Models running on the platform key are
    excluded — their failure isn't the user's key to fix."""
    from calypr_model import provider_of  # local: keeps the DSL-only import surface small

    on_file = set(keys or {})
    return {
        provider_of(m)
        for node in graph.nodes
        if isinstance(m := node.config.get("model"), str)
        if provider_of(m) in on_file
    }
