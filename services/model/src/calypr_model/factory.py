"""Resolve a model id to a provider client (CLAUDE-PLAN.md §10).

Phase 2: a single agent picks one provider by its model id. Per-agent multi-provider
selection is naturally supported later (each Agent node carries its own model id)."""

from __future__ import annotations

from calypr_model.anthropic_client import AnthropicModelClient
from calypr_model.base import ModelClient
from calypr_model.fake import FakeModelClient
from calypr_model.openai_client import OpenAIModelClient


def provider_of(model_id: str) -> str:
    m = model_id.lower()
    if m == "fake":
        return "fake"
    if m.startswith(("claude", "anthropic")):
        return "anthropic"
    if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt", "openai")):
        return "openai"
    return "openai"  # sensible default for unknown ids


def model_for(model_id: str) -> ModelClient:
    provider = provider_of(model_id)
    if provider == "fake":
        return FakeModelClient()
    if provider == "anthropic":
        return AnthropicModelClient()
    return OpenAIModelClient()
