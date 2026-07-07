"""The assistant's system prompt — built once from live contracts, never hand-written.

The GraphSpec schema, the node catalog, and the few-shot examples are all derived from the
DSL, the node registry, and real compiler templates. New node types or schema changes are
picked up automatically, so the prompt can't silently drift from what the compiler accepts
(AI-ASSISTANT-SPEC.md §5.1)."""

from __future__ import annotations

import json
from functools import lru_cache

from calypr_compiler.templates import market_research, rag, routing
from calypr_dsl import GraphSpec
from calypr_nodes import all_node_types

#: Node types the assistant must never place on a user's canvas in v1 (§5.1): generated
#: Python is an injection + quality risk. Still listed in the catalog so the model knows the
#: type exists — a hard rule forbids emitting it.
FORBIDDEN_NODE_TYPES = frozenset({"code"})

MAX_REPAIRS = 2


def _node_catalog() -> str:
    """One line per registered node type: id, description, and its config fields.

    Registry-derived so it always lists every node type (the `code` type included, then
    forbidden by rule)."""
    lines: list[str] = []
    for type_id, node_cls in sorted(all_node_types().items()):
        desc = node_cls.meta.description or node_cls.meta.label
        schema = node_cls.config_model.model_json_schema()
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        fields = []
        for name, info in props.items():
            tag = "" if name in required else "?"
            typ = info.get("type", info.get("anyOf", info.get("$ref", "any")))
            if isinstance(typ, list):
                typ = "/".join(str(t.get("type", "any")) for t in typ)
            fields.append(f"{name}{tag}:{typ}")
        forbidden = " [FORBIDDEN in v1 — never use]" if type_id in FORBIDDEN_NODE_TYPES else ""
        field_str = ", ".join(fields) if fields else "(no config)"
        lines.append(f"- {type_id}: {desc}{forbidden}\n    config: {field_str}")
    return "\n".join(lines)


def _few_shots() -> str:
    """2–3 (request, spec) pairs from real templates — they teach the wiring conventions
    (entry input node, `messages` channel with the append reducer, router `condition`
    edges, retriever→agent grounding)."""
    pairs = [
        ("I want a chatbot that answers questions from my documentation.", rag()),
        (
            "Route each message: summarize the long ones, translate the foreign ones.",
            routing(),
        ),
        (
            "Research a market and write a report using a team of specialist agents.",
            market_research(),
        ),
    ]
    blocks = []
    for request, spec in pairs:
        data = spec.model_dump(mode="json")
        for node in data.get("nodes", []):
            node.pop("position", None)  # layout is applied client-side
        blocks.append(
            f'User: "{request}"\nAssistant:\n{json.dumps(data, separators=(",", ":"))}'
        )
    return "\n\n".join(blocks)


_HARD_RULES = """\
HARD RULES (a violation makes the output unusable):
- Output EXACTLY ONE JSON object and nothing else: no prose, no explanation, no markdown fences.
- The object must match the GraphSpec schema above.
- Every edge `source` and `target` must reference a declared node `id`.
- Exactly ONE node of type "input", and it must be the graph `entry`.
- At least one node of type "output".
- NEVER use the "code" node type.
- Omit every `position` field — the canvas lays nodes out itself.
- Use the "messages" state channel with the "append" reducer for conversation history.
- Router out-edges must set a `condition` matching one of the router's branch names."""


@lru_cache(maxsize=1)
def system_prompt() -> str:
    """The cached system prompt. Pure function of the registry/DSL/templates at import."""
    schema = json.dumps(GraphSpec.model_json_schema(), separators=(",", ":"))
    return (
        "You are Calypr's graph assistant. You turn a user's request into ONE agent graph "
        "expressed as a GraphSpec JSON object. The graph compiles to LangGraph, so it must "
        "be valid and well-wired.\n\n"
        "GraphSpec JSON schema:\n"
        f"{schema}\n\n"
        "Node catalog (the only node types that exist):\n"
        f"{_node_catalog()}\n\n"
        "Examples of good graphs:\n"
        f"{_few_shots()}\n\n"
        f"{_HARD_RULES}"
    )
