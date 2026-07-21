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
        ("kimi-k3", "moonshot"),
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


def test_moonshot_falls_back_to_kimi_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Moonshot's console labels the credential KIMI_API_KEY; accept it as an alias so a
    fresh .env from their dashboard works without renaming."""
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi")
    assert model_for("kimi-k3")._client.api_key == "sk-kimi"


def test_moonshot_api_key_wins_over_kimi_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-moonshot")
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi")
    assert model_for("kimi-k3")._client.api_key == "sk-moonshot"


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


@pytest.mark.parametrize(
    ("model_id", "sends_temperature"),
    [
        ("kimi-k3", False),
        ("KIMI-K3", False),  # ids are matched case-insensitively
        ("o3-mini", False),
        ("kimi-k2.5", True),
        ("gpt-4o", True),
    ],
)
def test_temperature_omitted_for_fixed_temperature_models(
    model_id: str, sends_temperature: bool
) -> None:
    """kimi-k3 and the o-series 400 on any temperature but their default, so the field must
    be dropped for them and kept for everything else (verified live against kimi-k3)."""
    from calypr_model.openai_client import _accepts_temperature

    assert _accepts_temperature(model_id) is sends_temperature


@pytest.mark.parametrize(
    ("model_id", "sends_temperature"),
    [
        ("gpt-5.6-terra", False),  # "Only the default (1) value is supported" (verified live)
        ("gpt-5.6-sol", False),
        ("gpt-4o", True),
    ],
)
def test_gpt5_family_omits_temperature(model_id: str, sends_temperature: bool) -> None:
    from calypr_model.openai_client import _accepts_temperature

    assert _accepts_temperature(model_id) is sends_temperature


@pytest.mark.parametrize(
    ("model_id", "accepts"),
    [
        ("claude-opus-4-8", False),  # sampling params removed on Opus 4.7+ — sending one 400s
        ("claude-opus-4-7", False),
        ("claude-sonnet-5", False),
        ("claude-sonnet-4-5", True),  # older models still take it
        ("claude-3-5-haiku", True),
    ],
)
def test_anthropic_omits_temperature_on_opus_47_and_later(model_id: str, accepts: bool) -> None:
    from calypr_model.anthropic_client import _accepts_temperature

    assert _accepts_temperature(model_id) is accepts


@pytest.mark.parametrize(
    ("model_id", "needs_off"),
    [
        ("gpt-5.6-terra", True),
        ("gpt-5.6-sol", True),
        ("gpt-4o", False),
        ("kimi-k3", False),  # kimi does tool calls with reasoning ON — don't over-apply this
    ],
)
def test_gpt56_turns_reasoning_off_only_for_tool_calls(model_id: str, needs_off: bool) -> None:
    """gpt-5.6 rejects function tools on Chat Completions while reasoning is on. The flag must
    stay scoped to that family — applying it to kimi-k3 would silently disable its reasoning."""
    from calypr_model.openai_client import _needs_reasoning_off_for_tools

    assert _needs_reasoning_off_for_tools(model_id) is needs_off
