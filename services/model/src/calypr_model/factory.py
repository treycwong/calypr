"""Resolve a model id to a provider client (CLAUDE-PLAN.md §10).

Phase 2: a single agent picks one provider by its model id. Per-agent multi-provider
selection is naturally supported later (each Agent node carries its own model id).

Moonshot (Kimi) and DeepSeek both expose OpenAI-compatible Chat Completions APIs, so
they reuse `OpenAIModelClient` pointed at a different `base_url`. Base URLs and keys come
from the environment — never trust hard-coded defaults for a moving target; override with
`MOONSHOT_BASE_URL` / `DEEPSEEK_BASE_URL` when the providers change them."""

from __future__ import annotations

import os

from calypr_model.anthropic_client import AnthropicModelClient
from calypr_model.base import ModelClient
from calypr_model.fake import FakeModelClient
from calypr_model.image_client import FakeImageClient, OpenAIImageClient
from calypr_model.openai_client import OpenAIModelClient
from calypr_model.tts_client import FakeTTSClient, OpenAITTSClient

# Current defaults (verify against provider docs; override via env if they move).
_MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


def provider_of(model_id: str) -> str:
    m = model_id.lower()
    if m == "fake":
        return "fake"
    if m.startswith(("claude", "anthropic")):
        return "anthropic"
    if m.startswith(("kimi", "moonshot")):
        return "moonshot"
    if m.startswith("deepseek"):
        return "deepseek"
    if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt", "openai")):
        return "openai"
    return "openai"  # sensible default for unknown ids


def _key(provider: str, keys: dict[str, str] | None, *env_vars: str) -> str | None:
    """A workspace's BYO key for `provider` (overrides), else the first set server env var
    (fallback). Several env names are accepted per provider because Moonshot's own console
    hands out a key it calls `KIMI_API_KEY` while our routing name is `moonshot`."""
    if keys and keys.get(provider):
        return keys[provider]
    for env_var in env_vars:
        value = os.environ.get(env_var)
        if value:
            return value
    return None


def model_for(model_id: str, keys: dict[str, str] | None = None) -> ModelClient:
    """Resolve a model id to a provider client. `keys` (provider → API key) is a workspace's
    BYO credentials; when present for the resolved provider it overrides the server env, so a
    self-serve user runs on their own key. Absent → env, exactly as before (prod-safe)."""
    provider = provider_of(model_id)
    if provider == "fake":
        return FakeModelClient()
    if provider == "anthropic":
        return AnthropicModelClient(api_key=_key("anthropic", keys, "ANTHROPIC_API_KEY"))
    if provider == "moonshot":
        return OpenAIModelClient(
            api_key=_key("moonshot", keys, "MOONSHOT_API_KEY", "KIMI_API_KEY"),
            base_url=os.environ.get("MOONSHOT_BASE_URL", _MOONSHOT_BASE_URL),
        )
    if provider == "deepseek":
        return OpenAIModelClient(
            api_key=_key("deepseek", keys, "DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE_URL),
        )
    return OpenAIModelClient(api_key=_key("openai", keys, "OPENAI_API_KEY"))


def image_model_for(
    model_id: str, keys: dict[str, str] | None = None
) -> OpenAIImageClient | FakeImageClient:
    """Resolve an image-generation model id to a client — the image-modality sibling of
    `model_for`. `fake` → keyless deterministic client (tests/CI); everything else → OpenAI
    (gpt-image-1), on the workspace's BYO key if set else the env. Kept separate from
    `model_for` because image generation is a different provider surface (bytes + per-image
    usage), not the chat/stream protocol."""
    if model_id.lower().strip() == "fake":
        return FakeImageClient()
    return OpenAIImageClient(api_key=_key("openai", keys, "OPENAI_API_KEY"))


def tts_model_for(
    model_id: str, keys: dict[str, str] | None = None
) -> OpenAITTSClient | FakeTTSClient:
    """Resolve a text-to-speech model id to a client — the audio sibling of `image_model_for`.
    `fake` → keyless deterministic client (tests/CI); everything else → OpenAI (gpt-4o-mini-tts,
    tts-1, tts-1-hd) on the workspace's BYO key if set else the env. Separate seam because TTS
    returns bytes, not the chat/stream protocol."""
    if model_id.lower().strip() == "fake":
        return FakeTTSClient()
    return OpenAITTSClient(api_key=_key("openai", keys, "OPENAI_API_KEY"))
