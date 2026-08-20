"""The assistant's system prompt — built once from live contracts, never hand-written.

The GraphSpec schema, the node catalog, and the few-shot examples are all derived from the
DSL, the node registry, and real compiler templates. New node types or schema changes are
picked up automatically, so the prompt can't silently drift from what the compiler accepts
(AI-ASSISTANT-SPEC.md §5.1)."""

from __future__ import annotations

import json
from functools import lru_cache

from calypr_compiler.templates import (
    flashcards,
    image_generation,
    label_reader,
    market_research,
    notion_assistant,
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


def _german_flashcards() -> GraphSpec:
    """The flashcards template with the study subject filled in.

    Paired with a request that *names* a subject, so it teaches the model to specialize. The
    generic template prompt ("the learner names a topic") taught the opposite: given "flashcards
    for learning German" the model reproduced the topic-agnostic wording verbatim, and the first
    thing the finished app said was "what would you like to be quizzed on?" — to someone who had
    already answered that. The fenced card specimens are copied through untouched; they teach the
    format, and the format is the part that has to be byte-right."""
    spec = flashcards()
    for node in spec.nodes:
        if node.type == "agent":
            node.config["system_prompt"] = node.config["system_prompt"].replace(
                "You are a study coach. The learner names a topic; you drill them on it "
                "with flashcards, one small batch at a time, and adapt to what they miss.",
                "You are a German tutor. Drill the learner on German vocabulary and phrases "
                "with flashcards, one small batch at a time, and adapt to what they miss. "
                "Start straight away with common beginner words — never ask them what to "
                "study, they came here for German.",
            )
    return spec


def few_shot_pairs() -> list[tuple[str, GraphSpec]]:
    """The (request, spec) pairs the prompt teaches from.

    Public so tests can hold them to the same bar as a shipped starter: a few-shot is the
    model's only picture of a correct graph, so an invalid one doesn't just fail — it teaches
    the mistake. Two of these (`_anime_image`, `_spoken_assistant`) are built here rather than
    taken from `templates.py`, so nothing else covers them (`_german_flashcards` derives from
    one, but rewrites the part under test)."""
    return [
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
        # Tools: until this example existed, no few-shot contained a Tool node at all, and the
        # model reached for the one control-flow shape it *had* seen — a Router with a "notion"
        # branch. That compiles and runs, but binds the tools to the Router, which discards
        # them: the agent ends up with no tools and says it can't access Notion. This teaches
        # the ReAct loop instead — the Tool node hangs off the *agent*, with `tools`/`respond`
        # branches and an edge back.
        ("Make an assistant that can read my Notion workspace.", notion_assistant()),
        # Study cards. Without this the model built a plausible-looking "flashcard system" whose
        # agent emitted **bold** prose, so the UI had nothing to render and no way to keep score —
        # the cards are a *prompt* contract, and the model can't invent a contract it has never
        # seen. Carrying the whole `_CARD_PROTOCOL` into the few-shot is the point: it teaches the
        # exact fence, which is the one part that has to be byte-right.
        ("Create a flashcard system for learning German.", _german_flashcards()),
    ]


def _few_shots() -> str:
    """The pairs above, rendered into the prompt (layout stripped — it's applied client-side)."""
    blocks = []
    for request, spec in few_shot_pairs():
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
- Router out-edges must set a `condition` matching one of the router's branch names.
- Take an example's SHAPE, not its subject. When the user names a domain ("German", "biology",
  the AWS exam), the agent's `system_prompt` must name that domain and get to work on it — never
  ask the learner what to study when they have already said. Any fenced block inside an example
  prompt is a FORMAT specimen: reproduce it exactly, including its sample content, and change the
  wording around it.
- "evaluator" and "memory" are INTERNAL nodes: they write to their own channels (score /
  rationale, memory) and never to "messages", so nothing they produce reaches the user. Add them
  only when the user actually asks to score, grade, or remember — never as a quality flourish on
  a graph that just needs to answer. An evaluator dropped into a chat app costs a second model
  call per turn and shows the user nothing.
- A "tool" node must be wired FROM the agent/responder/revisor that will call it, never from a
  router: edge agent -> tool with condition "tools", edge agent -> next with condition
  "respond", and an edge tool -> agent to close the loop. Only the LLM node wired to a tool
  node can bind its tools; a router cannot. To give one agent several tools (say Notion and
  web search), add a separate tool node per provider and wire EACH of them to that same agent
  this way — the agent picks between them itself, so it needs no router to choose."""


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
