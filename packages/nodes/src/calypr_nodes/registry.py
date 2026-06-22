"""The node registry — the plugin backbone (CLAUDE-PLAN.md §5).

Each node type registers once with: metadata, a Pydantic config schema, read/write
channel declarations, and a `compile(cfg, ctx) -> node callable`. Registering a type is
all it takes for the compiler to handle it and (later) for the canvas to render it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from calypr_model import ModelClient
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
    KB retrievers and a credential vault are added in later phases.
    """

    model: ModelClient | None = None
    tools: list[dict] | None = None


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
