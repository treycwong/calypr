"""Execute compiled graphs — one-shot invoke and token-streaming run (CLAUDE-PLAN.md §8)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from calypr_compiler import compile_graph
from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from calypr_runtime.events import RunEvent


class RunError(Exception):
    """A run failure whose message is safe to show a client verbatim (no internals). The API
    layer surfaces `RunError.message` directly; any *other* exception becomes a generic message
    so raw tracebacks/provider errors never reach the public share surface."""


# Shown when a graph runs to the recursion limit. Cleaner than LangGraph's raw "Recursion limit
# of N reached…", but deliberately no longer *asserts* a cause: it used to say the graph "has a
# cycle with no exit", which is only one possibility and was wrong in the case that prompted
# this — a textbook ReAct graph whose Agent kept re-asking for the same tool because its preset
# discarded the result. Telling someone to remove a back-edge their graph needs sends them to
# rewrite the one part that was correct.
_LOOP_MESSAGE = (
    "This agent kept going without reaching an answer, so it was stopped. Usually one of: a "
    "loop with no way out, or a step that repeats because it never sees the previous result. "
    "Check the edges leaving your Agent, and that any Tool result feeds back into it."
)


#: Node types whose words are the run's prose. Media nodes (Image, TTS, 3D, Video) also emit
#: tokens, but those are the deliverable itself (a picture, a player), so they are never gated.
_TEXT_NODES = frozenset({"agent", "responder", "revisor"})


def silent_agents(spec: GraphSpec) -> frozenset[str]:
    """Agent nodes whose text is an intermediate step, not the answer, so it must not stream.

    An Agent is silent when another text node (Agent, Responder or Revisor) comes after it on
    the way to the Output: an orchestrator briefing its specialists, a triage step, a research
    draft an editor rewrites. Before this, every Agent streamed, so Trip planner opened with the
    orchestrator's brief and Market research showed all five drafts back to back (CAL-39).
    The silent node still runs, and is still metered: only its tokens are dropped, the same
    contract as the internal-node gate in `_llm.collect_text`.

    Deliberately narrow:
    - Only `agent` nodes are gated. A Reflexion Responder/Revisor pair keeps today's behaviour.
    - A node reaching *itself* (the ReAct loop through a Tool node) doesn't count.
    - If the rule would silence every text node (agents looping into each other, with no clear
      last speaker), nothing is gated, so a run can never go quiet."""
    by_id = {n.id: n for n in spec.nodes}
    succ: dict[str, set[str]] = {}
    pred: dict[str, set[str]] = {}
    for e in spec.edges:
        succ.setdefault(e.source, set()).add(e.target)
        pred.setdefault(e.target, set()).add(e.source)

    def walk(start: str, graph: dict[str, set[str]]) -> set[str]:
        seen: set[str] = set()
        stack = list(graph.get(start, ()))
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(graph.get(n, ()))
        return seen

    outputs = [n.id for n in spec.nodes if n.type == "output"]
    feeds_output: set[str] = set(outputs)
    for o in outputs:
        feeds_output |= walk(o, pred)

    text = {n.id for n in spec.nodes if n.type in _TEXT_NODES}
    silent = {
        n.id
        for n in spec.nodes
        if n.type == "agent"
        and any(d != n.id and d in text and d in feeds_output for d in walk(n.id, succ))
    }
    if text and not (text - silent):
        return frozenset()
    return frozenset(silent & set(by_id))


def _config(thread_id: str | None) -> dict:
    # recursion_limit bounds tool/reflection loops so a runaway graph stops cleanly.
    return {
        "configurable": {"thread_id": thread_id or str(uuid4())},
        "recursion_limit": 50,
    }


def _initial_state(user_input: str, images: list[str] | None) -> dict[str, Any]:
    """Seed state for one turn, `images` included **every** turn (empty when nothing is
    attached).

    `images` is a last-value channel and the thread is checkpointed, so seeding it only when
    present left the previous turn's photo in place: a text-only follow-up still "had" the old
    attachment, Upload re-sent it to the model, and an Image block set to use attachments would
    animate it again (CAL-61). A graph that declares no `images` channel ignores the key, so it
    sees exactly the state it always did."""
    return {"input": user_input, "images": list(images or [])}


async def run(
    spec: GraphSpec,
    ctx: NodeContext,
    user_input: str,
    *,
    images: list[str] | None = None,
    thread_id: str | None = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Compile + run to completion; return the final state."""
    compiled = compile_graph(spec, ctx, checkpointer=checkpointer or InMemorySaver())
    return await compiled.ainvoke(_initial_state(user_input, images), _config(thread_id))


async def run_stream(
    spec: GraphSpec,
    ctx: NodeContext,
    user_input: str,
    *,
    images: list[str] | None = None,
    thread_id: str | None = None,
    checkpointer: Any = None,
) -> AsyncIterator[RunEvent]:
    """Compile + run, yielding token/usage events as they arrive, then a final event."""
    compiled = compile_graph(spec, ctx, checkpointer=checkpointer or InMemorySaver())
    silent = silent_agents(spec)
    last_state: dict[str, Any] = {}
    try:
        async for mode, chunk in compiled.astream(
            _initial_state(user_input, images), _config(thread_id), stream_mode=["custom", "values"]
        ):
            if mode == "custom":
                kind = chunk.get("type")
                if kind == "token":
                    # Intermediate agents' words stay out of the chat (CAL-39); their usage events
                    # below are untouched, so metering never depends on what was shown.
                    if chunk.get("node_id") in silent:
                        continue
                    yield RunEvent(type="token", text=chunk.get("text", ""))
                elif kind == "usage":
                    yield RunEvent(type="usage", state=chunk)
                elif kind == "asset":
                    yield RunEvent(type="asset", state=chunk)
                elif kind == "node":
                    yield RunEvent(
                        type="node",
                        node_id=chunk.get("node_id", ""),
                        phase=chunk.get("phase", ""),
                    )
            elif mode == "values":
                last_state = chunk
    except GraphRecursionError as exc:
        # Surface a human message instead of LangGraph's raw recursion-limit error.
        raise RunError(_LOOP_MESSAGE) from exc
    yield RunEvent(type="final", output=last_state.get("output", ""), state=last_state)
