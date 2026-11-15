"""Only the answer streams: intermediate agents run and are metered, but their words stay out of
the chat (CAL-39).

Before this, every Agent streamed, so Trip planner opened with the orchestrator's brief to its
specialists and Customer support ran the triage note, the reply and the escalation summary
together into one bubble.
"""

from __future__ import annotations

import re

from calypr_compiler.templates import STARTERS
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import Done, TextDelta, Usage
from calypr_nodes import NodeContext
from calypr_runtime import run_stream
from calypr_runtime.run import silent_agents

_STATE = [
    StateChannel(key="input", type="string", reducer=Reducer.last),
    StateChannel(key="messages", type="messages", reducer=Reducer.append),
    StateChannel(key="output", type="string", reducer=Reducer.last),
]


class _RoleFake:
    """Replies `<role>` where the agent's system prompt says `ROLE:<role>`, so each agent's
    words are recognisable in the stream."""

    async def stream(self, *, model, messages, system="", tools=None, **_):
        role = (re.search(r"ROLE:(\w+)", system or "") or [None, "?"])[1]
        text = f"<{role}>"
        yield TextDelta(text=text)
        yield Usage(input_tokens=3, output_tokens=1)
        yield Done(text=text, tool_calls=[])


def _agent(node_id: str) -> NodeSpec:
    return NodeSpec(
        id=node_id,
        type="agent",
        config={
            "model": "fake",
            "system_prompt": f"ROLE:{node_id}",
            "input_channel": "messages",
            "output_channel": "messages",
        },
    )


def _io() -> list[NodeSpec]:
    into = {"input_channel": "input", "target_channel": "messages"}
    out = {"source_channel": "messages", "output_channel": "output"}
    return [
        NodeSpec(id="in", type="input", config=into),
        NodeSpec(id="out", type="output", config=out),
    ]


def _chain_spec(*agents: str) -> GraphSpec:
    path = ["in", *agents, "out"]
    pairs = zip(path, path[1:], strict=False)
    return GraphSpec(
        id="chain",
        name="chain",
        state=_STATE,
        nodes=[*_io(), *(_agent(a) for a in agents)],
        edges=[EdgeSpec(id=f"e{i}", source=a, target=b) for i, (a, b) in enumerate(pairs)],
        entry="in",
    )


async def test_only_the_last_agent_streams_but_every_agent_is_metered():
    spec = _chain_spec("brief", "draft", "final")
    events = [ev async for ev in run_stream(spec, NodeContext(model=_RoleFake()), "go")]

    streamed = "".join(e.text for e in events if e.type == "token")
    assert streamed == "<final>"
    # The silenced agents still ran, and their spend is still reported.
    metered = {e.state["node_id"] for e in events if e.type == "usage"}
    assert metered == {"brief", "draft", "final"}
    assert events[-1].type == "final"
    assert events[-1].output == "<final>"


async def test_a_single_agent_still_streams():
    spec = _chain_spec("solo")
    events = [ev async for ev in run_stream(spec, NodeContext(model=_RoleFake()), "go")]
    assert "".join(e.text for e in events if e.type == "token") == "<solo>"


def test_a_react_loop_through_a_tool_does_not_silence_the_agent():
    spec = next(g for g in STARTERS if g.id == "tpl-react")
    assert silent_agents(spec) == frozenset()


def test_agents_looping_into_each_other_are_never_all_silenced():
    """No clear last speaker: rather than go quiet, gate nothing (today's behaviour)."""
    spec = _chain_spec("a", "b")
    spec = spec.model_copy(
        update={"edges": [*spec.edges, EdgeSpec(id="back", source="b", target="a")]}
    )
    assert silent_agents(spec) == frozenset()


def test_an_agent_feeding_a_media_block_keeps_its_text():
    """Translate & speak shows the agent's transcript above the audio: TTS isn't a text node."""
    spec = next(g for g in STARTERS if g.id == "tpl-translate-speak")
    assert silent_agents(spec) == frozenset()


def test_the_starter_templates_have_one_voice_each():
    expected = {
        "tpl-trip-planner": {"orchestrator", "flights", "lodging", "activities", "dining"},
        "tpl-customer-support": {"intent", "escalation"},
        "tpl-market-research": {"research", "analysis", "writing", "critique"},
        "tpl-contract-review": {"clauses", "compliance", "risk", "summary"},
        "tpl-routing": set(),
        "tpl-reflexion": set(),
    }
    by_id = {g.id: g for g in STARTERS}
    for template, silent in expected.items():
        assert silent_agents(by_id[template]) == silent, template


def test_customer_support_ends_with_the_reply_not_the_reviewer():
    """The escalation reviewer used to run last, so the graph's output was its internal note."""
    spec = next(g for g in STARTERS if g.id == "tpl-customer-support")
    into_out = {e.source for e in spec.edges if e.target == "out"}
    assert into_out == {"response"}
