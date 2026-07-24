"""The Agent node must meter the model it *ran*, not the one its config stored.

`AgentConfig.model` defaults to `""` — inherit, resolved by `effective_model` through the
workspace default to `PLATFORM_DEFAULT_MODEL`. The usage payload used to report that raw `""`,
and `pricing.price_for("")` falls back to the most-expensive known rate so metering never
under-records. Combined, an ordinary inherited-model run was billed at roughly 163× its true
cost: in production this produced 38 usage rows priced at the maximum and over half of all
recorded platform spend. It was invisible while nothing read the number — and stops being
invisible the moment credits are enforced against real customers.
"""

from __future__ import annotations

from calypr_nodes import AgentConfig, NodeContext
from calypr_nodes.agent import AgentNode
from calypr_nodes.registry import PLATFORM_DEFAULT_MODEL, effective_model
from langchain_core.messages import HumanMessage


def _usage(captured: list[dict]) -> list[dict]:
    return [p for p in captured if p.get("type") == "usage"]


async def test_inherited_model_is_metered_as_the_resolved_id(monkeypatch):
    """The regression: `model: ""` must never reach the usage payload."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.agent.safe_stream_writer", lambda: captured.append)
    run = AgentNode.compile(AgentConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="hello")]})

    usage = _usage(captured)
    assert usage, "the agent node must emit a usage payload for metering"
    for u in usage:
        assert u["model"], "an empty model id is priced at the fail-closed maximum"
        assert u["model"] == "fake"


async def test_empty_config_model_resolves_to_the_workspace_default(monkeypatch):
    """Inherit → the workspace's choice, and *that* is what gets priced."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.agent.safe_stream_writer", lambda: captured.append)
    run = AgentNode.compile(AgentConfig(model=""), NodeContext(default_model="fake"))
    await run({"messages": [HumanMessage(content="hello")]})

    usage = _usage(captured)
    assert usage
    for u in usage:
        assert u["model"] == "fake"


def test_the_fallback_chain_never_yields_an_unpriceable_id():
    """The last link in `effective_model`'s chain must still be a real, priceable id.

    Asserted directly rather than by running a node: with no key configured, resolving the
    platform default constructs a client and raises before any usage is emitted, so a run-based
    version of this would pass for the wrong reason."""
    assert effective_model(NodeContext(), "") == PLATFORM_DEFAULT_MODEL
    assert effective_model(NodeContext(default_model="fake"), "") == "fake"
    assert effective_model(NodeContext(default_model="fake"), "gpt-4o") == "gpt-4o"
    assert PLATFORM_DEFAULT_MODEL, "an empty platform default would reintroduce the bug"
