"""Golden GraphSpec builders — the canonical fixtures used by tests and demos.

In Phase 2 these double as the seed for cross-language (Python + TS) fixture validation.
"""

from __future__ import annotations

from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel


def input_agent_output(
    *,
    model: str = "fake",
    system_prompt: str = "You are a helpful assistant.",
) -> GraphSpec:
    """The thinnest complete agent: Input → Agent → Output."""
    return GraphSpec(
        id="golden-input-agent-output",
        name="Input → Agent → Output",
        description="The thinnest complete agent.",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(
                id="agent",
                type="agent",
                config={
                    "model": model,
                    "system_prompt": system_prompt,
                    "input_channel": "messages",
                    "output_channel": "messages",
                },
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="out"),
        ],
        entry="in",
    )
