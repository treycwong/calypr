"""The node registry — the plugin backbone (CLAUDE-PLAN.md §5).

Each node type registers once with: metadata, a Pydantic config schema, read/write
channel declarations, and a `compile(cfg, ctx) -> node callable`. Registering a type is
all it takes for the compiler to handle it and (later) for the canvas to render it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from calypr_dsl import StateChannel
from calypr_model import ModelClient, image_model_for, model_for, tts_model_for
from pydantic import BaseModel

# A compiled node: reads the graph state, returns a partial state update.
NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class CodeFragment:
    """The generated Python for one node — a node function plus the imports it needs.

    The codegen service collects fragments, dedupes imports, and wires `fn_name` into the
    `StateGraph` (CLAUDE-PLAN realignment §Phase 3 / round-trip). For routing nodes, also
    emit a `route_{fn_name}` function and set `routing=True`; the service wires it via
    `add_conditional_edges`."""

    fn_name: str
    function: str  # full "def {fn_name}(state: State) -> dict: ..." source
    imports: list[str] = field(default_factory=list)
    routing: bool = False


@dataclass
class NodeContext:
    """Runtime dependencies injected into a node at compile time.

    Carries the model client and, for an LLM node wired to Tool nodes, the bound tool
    schemas (`{name, description, input_schema}`) the compiler resolves from the graph.
    `image_model`/`tts_model` are the same injection seam for the Image/Voice nodes (tests
    inject a Fake client so the starter/template test matrix never makes a real, billed API
    call regardless of the node's configured model — see `image_model_for_node`).
    KB retrievers and a credential vault are added in later phases.
    """

    model: ModelClient | None = None
    tools: list[dict] | None = None
    image_model: Any | None = None
    tts_model: Any | None = None


@dataclass
class CodegenContext:
    """Per-node context for `codegen()` — the codegen mirror of `NodeContext`.

    Currently the tool variable names an LLM node should `bind_tools([...])` (resolved from
    the graph by the codegen service), so generated code binds the same tools the compiler does.
    """

    tool_refs: list[str] = field(default_factory=list)


class NodeMeta(BaseModel):
    """Palette metadata for a node type (drives the canvas in Phase 2)."""

    label: str
    category: str
    icon: str = ""
    description: str = ""


class BaseNode:
    """Base class for node types. Subclasses set `type`, `meta`, `config_model`
    and implement `compile`."""

    type: ClassVar[str]
    meta: ClassVar[NodeMeta]
    config_model: ClassVar[type[BaseModel]]

    @classmethod
    def reads(cls, cfg: BaseModel) -> list[str]:
        return []

    @classmethod
    def writes(cls, cfg: BaseModel) -> list[str]:
        return []

    @classmethod
    def channels(cls, cfg: BaseModel) -> list[StateChannel]:
        """State channels this node *owns* — declared with their reducer so the engine can
        guarantee they exist even if the client's `state` omits them (e.g. a canvas that
        sends a fixed default state). Most nodes only use the common channels and return []."""
        return []

    @classmethod
    def compile(cls, cfg: BaseModel, ctx: NodeContext) -> NodeFn:  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def codegen(
        cls, cfg: BaseModel, fn_name: str, ctx: CodegenContext | None = None
    ) -> CodeFragment:  # pragma: no cover
        """Emit idiomatic, standalone Python for this node (the 'code' altitude).

        `ctx` carries per-node codegen info (e.g. bound tool names); most nodes ignore it."""
        raise NotImplementedError(f"node {cls.type!r} has no codegen yet")

    @classmethod
    def routing(
        cls, cfg: BaseModel, ctx: NodeContext
    ) -> Callable[[dict[str, Any]], str] | None:
        """If this node makes a conditional branch decision, return a path function
        `(state) -> branch_name`. The compiler wires it via `add_conditional_edges`,
        mapping branch names to the targets of this node's labelled out-edges. Normal
        nodes return None (plain control-flow edges)."""
        return None


_REGISTRY: dict[str, type[BaseNode]] = {}


def register(cls: type[BaseNode]) -> type[BaseNode]:
    """Class decorator: add a node type to the registry, keyed by `cls.type`."""
    if cls.type in _REGISTRY:
        raise ValueError(f"duplicate node type: {cls.type!r}")
    _REGISTRY[cls.type] = cls
    return cls


def get_node(node_type: str) -> type[BaseNode]:
    try:
        return _REGISTRY[node_type]
    except KeyError as exc:
        raise KeyError(f"unknown node type: {node_type!r}") from exc


def has_node(node_type: str) -> bool:
    return node_type in _REGISTRY


def all_node_types() -> dict[str, type[BaseNode]]:
    return dict(_REGISTRY)


def parse_config(node_type: str, raw: dict[str, Any]) -> BaseModel:
    """Validate a node's raw config dict against its registered schema."""
    return get_node(node_type).config_model.model_validate(raw)


def graph_channels(nodes, declared: list[StateChannel]) -> list[StateChannel]:
    """The full state for a graph: the declared channels plus any a node *owns* but the
    client omitted. Declared channels win on a key clash. This makes the engine robust to a
    client (e.g. the canvas) that sends an incomplete `state` — without it, a node that
    writes an undeclared channel (like a loop counter) silently loses every write."""
    by_key: dict[str, StateChannel] = {c.key: c for c in declared}
    for node in nodes:
        if not has_node(node.type):
            continue
        node_cls = get_node(node.type)
        try:
            cfg = node_cls.config_model.model_validate(node.config)
        except Exception:
            continue
        for ch in node_cls.channels(cfg):
            by_key.setdefault(ch.key, ch)
    return list(by_key.values())


def model_for_node(ctx: NodeContext, model_id: str) -> ModelClient:
    """Resolve the model for an LLM node: the injected client (tests) if present, otherwise
    the node's *own* provider from its `model` id. This lets each LLM node use its own model
    (e.g. a cheap Responder + a strong Revisor), instead of one model for the whole graph."""
    return ctx.model if ctx.model is not None else model_for(model_id)


def image_model_for_node(ctx: NodeContext, model_id: str):
    """Resolve the image client for an Image node: the injected client (tests) if present,
    otherwise the node's own provider from its `model` id. Mirrors `model_for_node`."""
    return ctx.image_model if ctx.image_model is not None else image_model_for(model_id)


def tts_model_for_node(ctx: NodeContext, model_id: str):
    """Resolve the TTS client for a Voice node: the injected client (tests) if present,
    otherwise the node's own provider from its `model` id. Mirrors `model_for_node`."""
    return ctx.tts_model if ctx.tts_model is not None else tts_model_for(model_id)
