"""A deterministic, key-free assistant for CI/e2e and offline demos (§9).

Maps keywords in the latest user message to a real template spec and emits the full event
sequence — so the panel is fully exercisable without any provider key."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from calypr_compiler.golden import input_agent_output
from calypr_compiler.templates import market_research, rag, routing
from calypr_dsl import GraphSpec

from calypr_assistant.events import AssistEvent, Graph, Note, Status, Usage

# Keyword → spec builder, checked in order (first match wins).
_KEYWORD_SPECS: list[tuple[tuple[str, ...], object]] = [
    (("rag", "knowledge", "docs", "documentation", "retriev"), rag),
    (("route", "classif", "translate", "summar"), routing),
    (
        ("team", "parallel", "research", "orchestrat", "worker", "multi-agent",
         "multi agent", "multiagent", "collaborat"),
        market_research,
    ),
]


def _select_spec(text: str) -> GraphSpec:
    low = text.lower()
    for keywords, builder in _KEYWORD_SPECS:
        if any(k in low for k in keywords):
            spec = builder()  # type: ignore[operator]
            break
    else:
        spec = input_agent_output()
    # The fake path is the keyless one (CI/e2e/offline), so every LLM node must run without a
    # provider key — force `fake` so "Try it" works immediately after a generate.
    for node in spec.nodes:
        if isinstance(node.config, dict) and "model" in node.config:
            node.config["model"] = "fake"
    return spec


class FakeAssistant:
    """Same event contract as `draft_graph`, but keyword-driven and offline."""

    async def draft(
        self,
        messages: list[dict],
        current_graph: GraphSpec | None = None,
    ) -> AsyncIterator[AssistEvent]:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") != "assistant"),
            "",
        )
        yield Status("drafting")
        spec = _select_spec(last_user)
        # Normalize like the real path: fresh id, no positions (layout is client-side).
        spec.id = uuid.uuid4().hex
        for node in spec.nodes:
            node.position = None
        yield Status("validating")
        yield Usage(
            input_tokens=len(last_user.split()),
            output_tokens=len(spec.nodes) * 8,
            model="fake",
        )
        kinds = ", ".join(sorted({n.type for n in spec.nodes}))
        yield Note(f"Proposed “{spec.name}” — {len(spec.nodes)} nodes ({kinds}).")
        yield Graph(spec)
