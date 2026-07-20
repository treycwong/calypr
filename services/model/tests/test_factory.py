"""Provider routing: model id prefixes resolve to the right client (no network)."""

from __future__ import annotations

import pytest
from calypr_model import (
    AnthropicModelClient,
    FakeModelClient,
    OpenAIModelClient,
    model_for,
    provider_of,
)


@pytest.mark.parametrize(
    ("model_id", "provider"),
    [
        ("fake", "fake"),
        ("claude-sonnet-4-5", "anthropic"),
        ("anthropic.foo", "anthropic"),
        ("kimi-k2", "moonshot"),
        ("moonshot-v1-8k", "moonshot"),
        ("deepseek-chat", "deepseek"),
        ("gpt-4.1-mini", "openai"),
        ("o3-mini", "openai"),
        ("something-unknown", "openai"),
    ],
)
def test_provider_of(model_id: str, provider: str) -> None:
    assert provider_of(model_id) == provider


def test_kimi_and_deepseek_reuse_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keys need to exist so AsyncOpenAI construction doesn't complain.
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert isinstance(model_for("kimi-k2"), OpenAIModelClient)
    assert isinstance(model_for("deepseek-chat"), OpenAIModelClient)


def test_default_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    # OpenAI/Anthropic SDKs demand a key at construction; a dummy is enough here.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(model_for("fake"), FakeModelClient)
    assert isinstance(model_for("claude-3"), AnthropicModelClient)
    assert isinstance(model_for("gpt-4o"), OpenAIModelClient)


def test_moonshot_base_url_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test")
    monkeypatch.setenv("MOONSHOT_BASE_URL", "https://example.test/v1")
    client = model_for("kimi-k2")
    assert str(client._client.base_url).rstrip("/") == "https://example.test/v1"


def test_byo_key_overrides_env(monkeypatch):
    """A workspace's BYO key wins over the server env for that provider (self-serve BYO-key)."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic")
    m = model_for("gpt-4o-mini", {"openai": "byo-openai"})
    assert m._client.api_key == "byo-openai"
    a = model_for("claude-sonnet-4-5", {"anthropic": "byo-anthropic"})
    assert a._client.api_key == "byo-anthropic"


def test_missing_byo_key_falls_back_to_env(monkeypatch):
    """No BYO key for the provider → the server env, exactly as before (prod-safe default)."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    assert model_for("gpt-4o-mini")._client.api_key == "env-openai"
    # A BYO map that doesn't include the resolved provider also falls back.
    assert model_for("gpt-4o-mini", {"anthropic": "x"})._client.api_key == "env-openai"
