"""The assistant's system prompt — built once from live contracts, never hand-written.

The GraphSpec schema, the node catalog, and the few-shot examples are all derived from the
DSL, the node registry, and real compiler templates. New node types or schema changes are
picked up automatically, so the prompt can't silently drift from what the compiler accepts
(AI-ASSISTANT-SPEC.md §5.1)."""

from __future__ import annotations

import json
from functools import lru_cache

from calypr_compiler.templates import (
    image_generation,
    label_reader,
    market_research,
    rag,
    routing,
    text_to_speech,
)
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec
from calypr_nodes import all_node_types

#: Node types the assistant must never place on a user's canvas in v1 (§5.1): generated
#: Python is an injection + quality risk. Still listed in the catalog so the model knows the
#: type exists — a hard rule forbids emitting it.
FORBIDDEN_NODE_TYPES = frozenset({"code"})

MAX_REPAIRS = 2


def _node_catalog() -> str:
    """Per registered node type: id, description, and its config fields — each with its own
    description when the schema carries one, so the model knows what a field is *for* (e.g. the
    Image node's `style`), not just its type.

    Registry-derived so it always lists every node type (the `code` type included, then
    forbidden by rule)."""
    lines: list[str] = []
    for type_id, node_cls in sorted(all_node_types().items()):
        desc = node_cls.meta.description or node_cls.meta.label
        schema = node_cls.config_model.model_json_schema()
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        field_lines = []
        for name, info in props.items():
            tag = "" if name in required else "?"
            typ = info.get("type", info.get("anyOf", info.get("$ref", "any")))
            if isinstance(typ, list):
                typ = "/".join(str(t.get("type", "any")) for t in typ)
            line = f"      - {name}{tag}: {typ}"
            field_desc = info.get("description")
            if field_desc:
                line += f" — {field_desc}"
            field_lines.append(line)
        forbidden = " [FORBIDDEN in v1 — never use]" if type_id in FORBIDDEN_NODE_TYPES else ""
        block = "\n".join(field_lines) if field_lines else "      (no config)"
        lines.append(f"- {type_id}: {desc}{forbidden}\n    config:\n{block}")
    return "\n".join(lines)


def _anime_image() -> GraphSpec:
    """The image_generation template with the Image node's `style` set — the few-shot's worked
    example of a specialized generator."""
    spec = image_generation()
    for node in spec.nodes:
        if node.type == "image":
            node.config["style"] = "anime style illustration, vibrant colors, cel shading"
    return spec


def _spoken_assistant() -> GraphSpec:
    """Answer, then read the answer aloud: Input → Agent → Voice(TTS) → Output. Teaches the model
    to chain a TTS node after an agent and to set `instructions` for a consistent voice."""
    base = text_to_speech()
    return GraphSpec(
        id="tpl-spoken-assistant",
        name="Spoken assistant",
        description="Answer the user, then speak the answer aloud.",
        state=base.state,
        nodes=[
            NodeSpec(id="in", type="input", config={"target_channel": "messages"}),
            NodeSpec(
                id="agent",
                type="agent",
                config={"model": "gpt-4o-mini", "system_prompt": "Answer concisely."},
            ),
            NodeSpec(
                id="tts",
                type="tts",
                config={
                    "model": "gpt-4o-mini-tts",
                    "voice": "alloy",
                    "instructions": "warm and friendly, natural pacing",
                },
            ),
            NodeSpec(id="out", type="output", config={"source_channel": "messages"}),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="tts"),
            EdgeSpec(id="e3", source="tts", target="out"),
        ],
        entry="in",
    )


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
        # A *specialized* image generator: the Image node's `style` fixes the look, so any prompt
        # ("a dog") comes out in that style — this teaches the model to set `style`, not add an
        # Agent, when the user wants a consistent visual style.
        ("Make an image generator that always produces anime-style art.", _anime_image()),
        # Audio out: chain a Voice (TTS) node after an agent, with `instructions` for the voice.
        ("Build an assistant that answers me and reads the answer out loud.", _spoken_assistant()),
        # Image in: an Upload block before the agent lets a vision model review attachments.
        ("Build an agent I can send receipts to and it itemises them.", label_reader()),
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
