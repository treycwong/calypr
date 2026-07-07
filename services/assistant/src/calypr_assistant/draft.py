"""The generation pipeline: messages -> a validated GraphSpec, streamed as events.

Draft with the model, parse defensively, validate with the same `validate_graph` the
compiler uses, and re-prompt with the issue list up to `MAX_REPAIRS` times. The canvas is
only ever handed a spec that passed validation (AI-ASSISTANT-SPEC.md §5)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from calypr_compiler import validate_graph
from calypr_dsl import GraphSpec
from calypr_model import Done, ModelClient, Msg, Role, TextDelta, model_for
from calypr_model import Usage as ModelUsage

from calypr_assistant.events import AssistEvent, Error, Graph, Note, Status, Usage
from calypr_assistant.prompt import FORBIDDEN_NODE_TYPES, MAX_REPAIRS, system_prompt

_MAX_TOKENS = 4096
_TEMPERATURE = 0.2


class ParseError(Exception):
    """The model's text could not be turned into an acceptable GraphSpec."""


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a model reply, tolerating stray prose or code fences."""
    t = text.strip()
    if t.startswith("```"):
        # drop the opening fence (``` or ```json) and the closing fence
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ParseError("no JSON object found in the model output")
    return t[start : end + 1]


def _parse_and_normalize(text: str) -> GraphSpec:
    """Parse -> GraphSpec, reject forbidden nodes, and normalize (fresh id, no positions)."""
    raw = _extract_json(text)
    try:
        spec = GraphSpec.model_validate_json(raw)
    except Exception as exc:  # pydantic ValidationError or JSON error
        raise ParseError(f"output is not a valid GraphSpec: {exc}") from exc

    bad = sorted({n.type for n in spec.nodes if n.type in FORBIDDEN_NODE_TYPES})
    if bad:
        raise ParseError(f"forbidden node type(s) used: {', '.join(bad)}")

    spec.id = uuid.uuid4().hex
    for node in spec.nodes:
        node.position = None
    return spec


def _summary(spec: GraphSpec) -> str:
    """A cheap, static note about the graph — avoids a second model call in v1."""
    kinds = ", ".join(sorted({n.type for n in spec.nodes}))
    return (
        f"Proposed “{spec.name}” — {len(spec.nodes)} nodes "
        f"({kinds}) and {len(spec.edges)} edges."
    )


def _user_messages(messages: list[dict], current_graph: GraphSpec | None) -> list[Msg]:
    """Conversation history verbatim; in refine mode, append the current graph as context."""
    out: list[Msg] = []
    for m in messages:
        role = Role.assistant if m.get("role") == "assistant" else Role.user
        out.append(Msg(role=role, content=m.get("content", "")))
    if current_graph is not None:
        out.append(
            Msg(
                role=Role.user,
                content=(
                    "Here is the current graph. Apply my request and produce the FULL "
                    "updated graph, not a diff:\n"
                    + json.dumps(current_graph.model_dump(mode="json"), separators=(",", ":"))
                ),
            )
        )
    return out


async def _complete(
    client: ModelClient, model_id: str, system: str, messages: list[Msg]
) -> tuple[str, ModelUsage | None]:
    """Run one streamed completion, accumulating text and usage."""
    parts: list[str] = []
    usage: ModelUsage | None = None
    async for ev in client.stream(
        model=model_id,
        messages=messages,
        system=system,
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    ):
        if isinstance(ev, TextDelta):
            parts.append(ev.text)
        elif isinstance(ev, ModelUsage):
            usage = ev
        elif isinstance(ev, Done) and not parts:
            parts.append(ev.text)
    return "".join(parts), usage


async def draft_graph(
    messages: list[dict],
    current_graph: GraphSpec | None,
    model_id: str,
    *,
    client: ModelClient | None = None,
) -> AsyncIterator[AssistEvent]:
    """Draft (and repair) a GraphSpec, streaming status/note/graph/usage/error events."""
    client = client or model_for(model_id)
    system = system_prompt()
    convo = _user_messages(messages, current_graph)

    yield Status("drafting")
    last_message = "the assistant could not produce a valid graph"
    last_issues: list[dict] = []

    for attempt in range(MAX_REPAIRS + 1):
        text, usage = await _complete(client, model_id, system, convo)
        if usage is not None:
            yield Usage(usage.input_tokens, usage.output_tokens, model_id)

        try:
            spec = _parse_and_normalize(text)
        except ParseError as exc:
            last_message = str(exc)
            last_issues = []
            convo.append(Msg(role=Role.assistant, content=text))
            convo.append(
                Msg(
                    role=Role.user,
                    content=f"That was invalid: {exc}. Return ONLY the corrected GraphSpec JSON.",
                )
            )
            if attempt < MAX_REPAIRS:
                yield Status("repairing")
            continue

        yield Status("validating")
        issues = validate_graph(spec)
        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            yield Note(_summary(spec))
            yield Graph(spec)
            return

        last_message = "the drafted graph failed validation"
        last_issues = [i.model_dump() for i in errors]
        issue_text = "; ".join(f"[{i.code}] {i.message}" for i in errors)
        convo.append(Msg(role=Role.assistant, content=text))
        convo.append(
            Msg(
                role=Role.user,
                content=(
                    f"The graph has validation errors: {issue_text}. "
                    "Fix these and return ONLY the full corrected GraphSpec JSON."
                ),
            )
        )
        if attempt < MAX_REPAIRS:
            yield Status("repairing")

    yield Error(message=last_message, issues=last_issues)
