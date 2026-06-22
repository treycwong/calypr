"""Agent-type presets (Russell & Norvig ladder): every type compiles + runs with a fake
model; reflection's critique→revise loop terminates and actually iterates; utility-based
keeps the best candidate; simple-reflex forgets history (latest input only)."""

from __future__ import annotations

import pytest
from calypr_model import Done, FakeModelClient, Msg, Role, TextDelta
from calypr_nodes import AgentConfig, NodeContext
from calypr_nodes.agent import AgentNode
from langchain_core.messages import AIMessage, HumanMessage

AGENT_TYPES = [
    "simple_reflex",
    "model_based",
    "goal_based",
    "utility_based",
    "learning",
    "reflection",
]


class SpyModel:
    """Records each call and replies from a script (cycling on the last entry), so tests
    can count loop iterations and inspect the messages a preset actually sends."""

    def __init__(self, replies: list[str] | None = None) -> None:
        self.calls: list[list[Msg]] = []
        self._replies = list(replies) if replies else None

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls.append(list(messages))
        if self._replies is not None:
            text = self._replies[min(len(self.calls) - 1, len(self._replies) - 1)]
        else:
            last_user = next(
                (m.content for m in reversed(messages) if m.role == Role.user), ""
            )
            text = f"Echo: {last_user}"
        for i in range(0, len(text), 4):
            yield TextDelta(text=text[i : i + 4])
        yield Done(text=text, tool_calls=[])


@pytest.mark.parametrize("agent_type", AGENT_TYPES)
async def test_every_agent_type_compiles_and_runs(agent_type):
    ctx = NodeContext(model=FakeModelClient(reply="ok"))
    run = AgentNode.compile(AgentConfig(agent_type=agent_type, model="x"), ctx)
    update = await run({"messages": [HumanMessage(content="hello")]})
    msg = update["messages"][-1]
    assert isinstance(msg, AIMessage)
    assert msg.content == "ok"


async def test_reflection_loop_iterates_and_terminates():
    spy = SpyModel()  # echoes; bounded loop must terminate
    cfg = AgentConfig(agent_type="reflection", model="x", max_reflections=2)
    update = await AgentNode.compile(cfg, NodeContext(model=spy))(
        {"messages": [HumanMessage(content="draft this")]}
    )
    # 1 generation + (critique + revise) per reflection → 1 + 2*2 = 5 calls (it iterated).
    assert len(spy.calls) == 5
    assert update["messages"][-1].content == "Echo: draft this"


async def test_reflection_with_zero_reflections_is_a_single_call():
    spy = SpyModel()
    cfg = AgentConfig(agent_type="reflection", model="x", max_reflections=0)
    await AgentNode.compile(cfg, NodeContext(model=spy))(
        {"messages": [HumanMessage(content="hi")]}
    )
    assert len(spy.calls) == 1


async def test_utility_based_keeps_the_strongest_candidate():
    spy = SpyModel(replies=["short", "the longest answer", "mid"])
    cfg = AgentConfig(agent_type="utility_based", model="x", num_candidates=3)
    update = await AgentNode.compile(cfg, NodeContext(model=spy))(
        {"messages": [HumanMessage(content="q")]}
    )
    assert len(spy.calls) == 3  # generated num_candidates
    assert update["messages"][-1].content == "the longest answer"


async def test_simple_reflex_forgets_history():
    spy = SpyModel()
    cfg = AgentConfig(agent_type="simple_reflex", model="x")
    history = [
        HumanMessage(content="first question"),
        AIMessage(content="first answer"),
        HumanMessage(content="second question"),
    ]
    await AgentNode.compile(cfg, NodeContext(model=spy))({"messages": history})
    sent = spy.calls[0]
    assert len(sent) == 1  # latest input only — no memory
    assert sent[0].role == Role.user
    assert sent[0].content == "second question"


async def test_model_based_keeps_history():
    spy = SpyModel()
    cfg = AgentConfig(agent_type="model_based", model="x")
    history = [
        HumanMessage(content="first question"),
        AIMessage(content="first answer"),
        HumanMessage(content="second question"),
    ]
    await AgentNode.compile(cfg, NodeContext(model=spy))({"messages": history})
    assert len(spy.calls[0]) == 3  # full conversation state
