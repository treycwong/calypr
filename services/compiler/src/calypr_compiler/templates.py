"""Archetype templates — the Russell & Norvig agent ladder as starter graphs.

Six ready-to-run GraphSpecs spanning the simple→complex gradient the wedge plan wants:
each is a valid graph that compiles, runs, and round-trips to ownable Python. They double
as the canvas's starter gallery (served by the API) and as a compile/run test matrix."""

from __future__ import annotations

from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel

_BASE_STATE = [
    StateChannel(key="input", type="string", reducer=Reducer.last),
    StateChannel(key="messages", type="messages", reducer=Reducer.append),
    StateChannel(key="output", type="string", reducer=Reducer.last),
]
_MEMORY_STATE = [*_BASE_STATE, StateChannel(key="memory", type="list", reducer=Reducer.append)]
_EVAL_STATE = [
    *_BASE_STATE,
    StateChannel(key="score", type="number", reducer=Reducer.last),
    StateChannel(key="rationale", type="string", reducer=Reducer.last),
]


def _input() -> NodeSpec:
    return NodeSpec(
        id="in", type="input", config={"input_channel": "input", "target_channel": "messages"}
    )


def _output(source: str = "messages") -> NodeSpec:
    return NodeSpec(
        id="out", type="output", config={"source_channel": source, "output_channel": "output"}
    )


def _agent(agent_type: str, **config) -> NodeSpec:
    return NodeSpec(
        id="agent",
        type="agent",
        config={
            "agent_type": agent_type,
            "model": "fake",
            "input_channel": "messages",
            "output_channel": "messages",
            **config,
        },
    )


def _chain(*node_ids: str) -> list[EdgeSpec]:
    return [
        EdgeSpec(id=f"e{i}", source=a, target=b)
        for i, (a, b) in enumerate(zip(node_ids, node_ids[1:], strict=False), start=1)
    ]


def simple_reflex() -> GraphSpec:
    return GraphSpec(
        id="tpl-simple-reflex",
        name="Simple reflex",
        description="Reacts to the latest input — no memory. The thinnest agent.",
        state=_BASE_STATE,
        nodes=[_input(), _agent("simple_reflex"), _output()],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def model_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-model-based",
        name="Model-based reflex",
        description="Remembers the conversation via an explicit Memory buffer.",
        state=_MEMORY_STATE,
        nodes=[
            _input(),
            NodeSpec(
                id="memory",
                type="memory",
                config={
                    "operation": "buffer",
                    "input_channel": "messages",
                    "memory_channel": "memory",
                },
            ),
            _agent("model_based"),
            _output(),
        ],
        edges=_chain("in", "memory", "agent", "out"),
        entry="in",
    )


def goal_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-goal-based",
        name="Goal-based",
        description="Plans toward a stated goal, then acts.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _agent("goal_based", goal="Resolve the user's request completely."),
            _output(),
        ],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def utility_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-utility-based",
        name="Utility-based",
        description="Generates several answers, keeps the best, and scores it with an Evaluator.",
        state=_EVAL_STATE,
        nodes=[
            _input(),
            _agent("utility_based", num_candidates=3),
            NodeSpec(
                id="eval",
                type="evaluator",
                config={"model": "fake", "input_channel": "messages"},
            ),
            _output(),
        ],
        edges=_chain("in", "agent", "eval", "out"),
        entry="in",
    )


def reflection() -> GraphSpec:
    return GraphSpec(
        id="tpl-reflection",
        name="Reflection",
        description="Answers, then critiques and revises itself before replying.",
        state=_BASE_STATE,
        nodes=[_input(), _agent("reflection", max_reflections=2), _output()],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def learning() -> GraphSpec:
    return GraphSpec(
        id="tpl-learning",
        name="Learning (experimental)",
        description="Summarises the conversation into memory and adapts from it.",
        state=_MEMORY_STATE,
        nodes=[
            _input(),
            NodeSpec(
                id="memory",
                type="memory",
                config={
                    "operation": "summary",
                    "model": "fake",
                    "input_channel": "messages",
                    "memory_channel": "memory",
                },
            ),
            _agent("learning"),
            _output(),
        ],
        edges=_chain("in", "memory", "agent", "out"),
        entry="in",
    )


def react() -> GraphSpec:
    return GraphSpec(
        id="tpl-react",
        name="ReAct",
        description="Reason + act: the agent calls tools (web search) in a loop, then answers.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _agent(
                "model_based",
                system_prompt=(
                    "You are a research assistant. Use the web_search tool when you need "
                    "facts, then answer from what you found."
                ),
            ),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="tools", condition="tools"),
            EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
            EdgeSpec(id="e4", source="tools", target="agent"),  # the ReAct loop
        ],
        entry="in",
    )


# Ordered simple→complex — the wedge gradient the canvas gallery presents.
TEMPLATES: list[GraphSpec] = [
    simple_reflex(),
    model_based(),
    goal_based(),
    utility_based(),
    reflection(),
    learning(),
    react(),
]
