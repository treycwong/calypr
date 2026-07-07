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
from calypr_model.openai_client import OpenAIModelClient

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


def model_for(model_id: str) -> ModelClient:
    provider = provider_of(model_id)
    if provider == "fake":
        return FakeModelClient()
    if provider == "anthropic":
        return AnthropicModelClient()
    if provider == "moonshot":
        return OpenAIModelClient(
            api_key=os.environ.get("MOONSHOT_API_KEY"),
            base_url=os.environ.get("MOONSHOT_BASE_URL", _MOONSHOT_BASE_URL),
        )
    if provider == "deepseek":
        return OpenAIModelClient(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE_URL),
        )
    return OpenAIModelClient()
