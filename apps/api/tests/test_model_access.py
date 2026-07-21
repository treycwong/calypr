"""Frontier models are BYO-key only (see `calypr_api.model_access`)."""

import pytest
from calypr_api import engine, model_access
from calypr_api.main import app
from calypr_api.model_access import (
    FALLBACK_MODEL,
    frontier_key_error,
    frontier_provider,
    frontier_substitution_notice,
    is_frontier,
    missing_frontier_keys,
    substitute_missing_frontier_models,
)
from calypr_api.pricing import cost_usd, platform_cost_usd
from calypr_compiler.golden import input_agent_output
from calypr_dsl import GraphSpec, NodeSpec
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize(
    ("model_id", "provider"),
    [
        ("kimi-k3", "moonshot"),
        ("KIMI-K3", "moonshot"),
        ("kimi-k3-0711-preview", "moonshot"),  # dated ids are prefix-matched
        ("gpt-5.6-terra", "openai"),
        ("gpt-5.6-sol", "openai"),  # the whole 5.6 family is gated, not just the tier we offer
        ("claude-opus-4-8", "anthropic"),
        ("kimi-k2.5", None),  # the cheap K-family stays on the platform key
        ("gpt-4o", None),  # the models we serve on the platform key are NOT frontier
        ("gpt-4o-mini", None),
        ("claude-sonnet-4-5", None),
        ("fake", None),
    ],
)
def test_frontier_provider(model_id: str, provider: str | None) -> None:
    assert frontier_provider(model_id) == provider
    assert is_frontier(model_id) is (provider is not None)


def test_missing_frontier_keys_flags_only_unkeyed_frontier_models() -> None:
    graph = input_agent_output(model="kimi-k3")
    assert missing_frontier_keys(graph, None) == [("kimi-k3", "moonshot")]
    assert missing_frontier_keys(graph, {"openai": "sk-x"}) == [("kimi-k3", "moonshot")]
    # Key on file → the run may proceed.
    assert missing_frontier_keys(graph, {"moonshot": "sk-x"}) == []
    # Non-frontier graphs are never gated, with or without keys.
    assert missing_frontier_keys(input_agent_output(model="gpt-4o"), None) == []


def test_frontier_key_error_names_the_model_and_where_to_fix_it() -> None:
    msg = frontier_key_error([("kimi-k3", "moonshot")])
    assert "kimi-k3" in msg
    assert "Moonshot" in msg
    assert "Settings" in msg


def test_frontier_usage_is_free_to_the_platform() -> None:
    """BYO-key tokens bill the workspace's own provider account, not ours — so they must add
    $0 to `run.cost_usd` or one heavy user could trip the platform-wide spend cap."""
    assert platform_cost_usd("kimi-k3", 1_000_000, 1_000_000) == 0.0
    # The true provider rate is still recorded for reference, and non-frontier is unchanged.
    assert cost_usd("kimi-k3", 1_000_000, 1_000_000) == pytest.approx(18.0)
    assert platform_cost_usd("gpt-5.6-terra", 1_000_000, 1_000_000) == 0.0
    assert platform_cost_usd("claude-opus-4-8", 1_000_000, 1_000_000) == 0.0
    assert platform_cost_usd("gpt-4o", 1_000_000, 0) == cost_usd("gpt-4o", 1_000_000, 0)


@pytest.fixture
def no_byo_keys(monkeypatch: pytest.MonkeyPatch):
    """Pin the workspace to *no* stored keys. Without this the test reads whatever the local
    dev workspace happens to have saved, so it would pass or fail depending on the developer's
    own Settings → API Keys state."""
    monkeypatch.setattr(engine, "resolve_model_keys", lambda _ws: {})


def test_run_without_a_key_substitutes_the_fallback_and_says_so(
    no_byo_keys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing key degrades the run to the cheap platform model instead of dead-ending — but
    the notice is mandatory. Without it the user gets gpt-4o-mini output believing it came from
    the frontier model they picked, and exports a graph that behaves differently.

    The fallback is pinned to the keyless `fake` model for the duration: the real one is
    gpt-4o-mini, which needs an OPENAI_API_KEY that CI does not have. Asserting on a live
    provider call would make this test pass or fail on the environment rather than on the
    substitution it exists to check (`test_the_fallback_model_is_itself_never_frontier` and the
    pricing tests cover the real constant)."""
    monkeypatch.setattr(model_access, "FALLBACK_MODEL", "fake")
    graph = input_agent_output(model="kimi-k3").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hello"})
    assert r.status_code == 200
    body = r.text
    assert '"type": "notice"' in body
    assert "kimi-k3" in body and "Settings" in body
    # The run still produced output rather than dead-ending.
    assert '"type": "final"' in body
    # …and it never errored.
    assert '"type": "error"' not in body


def test_substitution_rewrites_only_the_unkeyed_frontier_nodes() -> None:
    """A graph mixing a keyed frontier model, an unkeyed one, and a platform model must come
    back with exactly one node rewritten."""
    graph = input_agent_output(model="fake")
    graph.nodes[0].config["model"] = "kimi-k3"  # unkeyed → substituted
    graph.nodes.append(
        NodeSpec(id="a2", type="agent", config={"model": "claude-opus-4-8"})
    )  # keyed → untouched
    graph.nodes.append(NodeSpec(id="a3", type="agent", config={"model": "gpt-4o"}))  # platform
    swapped, substituted = substitute_missing_frontier_models(graph, {"anthropic": "sk-x"})
    models = [n.config.get("model") for n in swapped.nodes]
    assert models[0] == FALLBACK_MODEL
    assert "claude-opus-4-8" in models and "gpt-4o" in models
    assert substituted == [("kimi-k3", "moonshot")]
    # The caller's graph is not mutated in place — the swap returns a copy.
    assert graph.nodes[0].config["model"] == "kimi-k3"


def test_no_substitution_when_every_key_is_on_file() -> None:
    graph = input_agent_output(model="fake")
    graph.nodes[0].config["model"] = "kimi-k3"
    swapped, substituted = substitute_missing_frontier_models(graph, {"moonshot": "sk-x"})
    assert substituted == []
    assert swapped is graph  # untouched, not even copied


def test_run_with_frontier_model_proceeds_once_the_key_is_on_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of the refusal: a stored moonshot key clears the gate. Uses `fake` for the
    actual node so nothing is sent to a provider — the assertion is about the gate, not the run."""
    monkeypatch.setattr(engine, "resolve_model_keys", lambda _ws: {"moonshot": "sk-byo"})
    graph = input_agent_output(model="fake").model_dump()
    graph["nodes"] = [
        {**n, "config": {**n["config"], "model": "kimi-k3"}} if n["type"] == "agent" else n
        for n in graph["nodes"]
    ]
    assert missing_frontier_keys(GraphSpec(**graph), {"moonshot": "sk-byo"}) == []


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("gpt-5.6-terra", (2.50, 15.00)),
        ("gpt-5.6-sol", (5.00, 30.00)),
        ("gpt-5.6-luna", (1.00, 6.00)),
        ("claude-opus-4-8", (5.00, 25.00)),
    ],
)
def test_frontier_models_are_priced_not_failing_closed(
    model_id: str, expected: tuple[float, float]
) -> None:
    """Each frontier model needs its own rate: the fail-closed fallback is the most expensive
    known pair, which would badly misreport what a BYO-key run actually cost the workspace."""
    from calypr_api.pricing import price_for

    price = price_for(model_id)
    assert (price.input_per_1m, price.output_per_1m) == expected


@pytest.mark.parametrize(
    ("provider", "label"),
    [("openai", "OpenAI"), ("anthropic", "Anthropic"), ("moonshot", "Moonshot")],
)
def test_error_copy_uses_real_provider_names(provider: str, label: str) -> None:
    """`.title()` renders "Openai"; the message is user-facing, so it uses display names and
    "your <Provider> key" rather than "a/an", which can't agree across every provider."""
    msg = frontier_key_error([("some-model", provider)])
    assert f"your {label} key" in msg
    assert "a Anthropic" not in msg and "Openai" not in msg


def test_the_fallback_model_is_itself_never_frontier() -> None:
    """Guards the obvious foot-gun: a fallback that needed its own BYO key would loop."""
    assert frontier_provider(FALLBACK_MODEL) is None


def test_substitution_notice_names_both_models_and_the_fix() -> None:
    msg = frontier_substitution_notice([("kimi-k3", "moonshot")])
    assert FALLBACK_MODEL in msg and "kimi-k3" in msg
    assert "Moonshot" in msg and "Settings" in msg
