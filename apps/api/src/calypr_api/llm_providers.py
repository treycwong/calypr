"""The LLM providers shown in Settings → Workspace, and whether each is actually usable yet.

The catalogue is served from the API rather than hard-coded in the web app so that "can I save a
key for this?" has exactly one answer. `status` is the honest state of the *backend*:

- `available` — the model factory can route to it and `PUT /provider-keys/{provider}` accepts it,
  so the key input is live.
- `coming_soon` — shown so the roadmap is visible, but the input is disabled and no key can be
  stored. Storing a credential we have no code path to use would be a liability, not a feature.

Flipping a row to `available` is the last step of wiring a provider, not the first: it must have a
client in `calypr_model.factory`, a price in `pricing.MODEL_PRICES`, and membership in
`schemas.PROVIDER_KEY_PROVIDERS`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LLMProvider(BaseModel):
    """One row in the provider list."""

    provider: str
    label: str
    #: The headline model this provider's key unlocks — what the user is really choosing.
    model_label: str
    status: Literal["available", "coming_soon"]
    #: Shown under the row when the provider isn't usable yet. Empty when it is.
    note: str = ""


PROVIDER_CATALOG: list[LLMProvider] = [
    LLMProvider(
        provider="moonshot",
        label="Moonshot (Kimi)",
        model_label="kimi-k3",
        status="available",
    ),
    LLMProvider(
        provider="openai",
        label="OpenAI",
        # No OpenAI *frontier* model is offered right now (GPT 5.6 Terra was pulled), but the
        # row stays live: an OpenAI key is the most useful one to store, because gpt-4o-mini is
        # both the default model and the fallback every un-keyed frontier run lands on.
        model_label="GPT-4o · GPT-4o mini",
        status="available",
        note="GPT 5.6 support is in progress.",
    ),
    LLMProvider(
        provider="anthropic",
        label="Anthropic",
        model_label="Claude Opus 4.8",
        status="available",
    ),
    LLMProvider(
        provider="google",
        label="Google",
        model_label="Gemini Pro",
        status="coming_soon",
        # Unlike the two above, this one has no client in the model factory at all.
        note="Gemini support is in progress.",
    ),
]

#: Providers whose key input is live. Everything else renders disabled.
AVAILABLE_PROVIDERS = frozenset(p.provider for p in PROVIDER_CATALOG if p.status == "available")


def llm_providers() -> list[LLMProvider]:
    return PROVIDER_CATALOG
