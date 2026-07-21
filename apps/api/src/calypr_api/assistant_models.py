"""The models a workspace may pick for the AI assistant (Settings → Workspace).

An explicit allow-list rather than "any string the client sends": the value is written to the
DB and later fed to the model factory, so an unchecked field would let a caller point the
assistant at an arbitrary model id — including expensive ones we don't price. Keep it in step
with the canvas picker in `apps/web/src/lib/graph.ts`.

Frontier entries carry a `byo_provider`: they run only on the workspace's own key
(`model_access`), so the settings picker disables them until that key is on file, and `/assist`
refuses them otherwise — same rule the canvas already applies to a graph's Agent nodes.
"""

from __future__ import annotations

from pydantic import BaseModel

from calypr_api.model_access import frontier_provider

#: (model id, human label). "" is the "inherit the server default" sentinel and is always valid.
ASSISTANT_MODELS: list[tuple[str, str]] = [
    ("", "Server default"),
    ("fake", "Fake (no key, deterministic)"),
    ("gpt-4o-mini", "OpenAI · gpt-4o-mini"),
    ("gpt-4o", "OpenAI · gpt-4o"),
    ("claude-sonnet-4-5", "Anthropic · claude-sonnet-4-5"),
    ("kimi-k3", "Moonshot · kimi-k3 (reasoning, 1M ctx)"),
    ("claude-opus-4-8", "Anthropic · Claude Opus 4.8"),
]

ASSISTANT_MODEL_IDS = frozenset(m for m, _ in ASSISTANT_MODELS)


class AssistantModelOption(BaseModel):
    """One choice in the Settings picker. `byo_provider` set ⇒ needs that provider's BYO key."""

    value: str
    label: str
    byo_provider: str | None = None


def assistant_model_options() -> list[AssistantModelOption]:
    return [
        AssistantModelOption(value=v, label=label, byo_provider=frontier_provider(v))
        for v, label in ASSISTANT_MODELS
    ]


def is_allowed(model_id: str) -> bool:
    return model_id in ASSISTANT_MODEL_IDS
