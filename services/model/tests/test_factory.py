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
