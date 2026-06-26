"""Router / If-Else node — conditional control flow (Phase 4 keystone).

The node is a passthrough; the *decision* is `routing()`, which the compiler wires via
`add_conditional_edges` to the targets of this node's labelled out-edges (the edge's
`condition` is the branch name).

Two kinds:
- `rules` — small Python predicates over `state`, gated behind the same trusted flag as
  Custom Code (they use `eval`).
- `llm` — a classifier (the slide's "routing agent"): the node body asks a model to pick the
  best branch for the latest input and writes it to a visible `route_channel` (`task_type`);
  `routing()` then reads that channel. Keyless/deterministic with the fake model (→ default).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from calypr_dsl import Reducer, StateChannel
from calypr_model import Msg, Role
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._llm import collect_text
from calypr_nodes.code import custom_code_allowed
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    model_for_node,
    register,
)

_SAFE_BUILTINS = {
    "len": len,
    "any": any,
    "all": all,
    "str": str,
    "int": int,
    "min": min,
    "max": max,
}


def _eval_rule(expr: str, state: dict[str, Any]) -> bool:
    try:
        return bool(
            eval(expr, {"__builtins__": {}}, {"state": state, **_SAFE_BUILTINS})  # noqa: S307
        )
    except Exception:
        return False


def _last_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        last = value[-1]
        return getattr(last, "content", str(last))
    return ""


class Branch(BaseModel):
    name: str  # must match an outgoing edge's `condition`
    # rules kind: a Python expression over `state`, e.g. '"refund" in state["input"]'.
    # llm kind: a natural-language description of what belongs in this branch.
    when: str = ""


class RouterConfig(BaseModel):
    kind: Literal["rules", "llm"] = "rules"
    input_channel: str = "messages"
    branches: list[Branch] = []
    default: str = ""  # branch name to use when none match
    model: str = "fake"  # llm kind: the classifier model
    route_channel: str = "task_type"  # llm kind: where the chosen branch is written


def _classify_prompt(cfg: RouterConfig) -> str:
    names = ", ".join(b.name for b in cfg.branches)
    options = "\n".join(
        f"- {b.name}: {b.when}" if b.when else f"- {b.name}" for b in cfg.branches
    )
    return (
        "You are a routing classifier. Read the user's request and choose the single best "
        f"category. Reply with ONLY the category name, exactly one of: {names}.\n"
        f"Categories:\n{options}"
    )


def _pick_branch(reply: str, cfg: RouterConfig, default: str) -> str:
    low = reply.lower()
    for b in cfg.branches:
        if b.name and b.name.lower() in low:
            return b.name
    return default


@register
class RouterNode(BaseNode):
    type = "router"
    meta = NodeMeta(
        label="If-Else",
        category="control",
        icon="git-branch",
        description="Branch the flow on a condition (Python rules or an LLM classifier).",
    )
    config_model = RouterConfig

    @classmethod
    def reads(cls, cfg: RouterConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: RouterConfig) -> list[str]:
        return [cfg.route_channel] if cfg.kind == "llm" else []

    @classmethod
    def channels(cls, cfg: RouterConfig) -> list[StateChannel]:
        if cfg.kind == "llm":
            return [
                StateChannel(key=cfg.route_channel, type="string", reducer=Reducer.last)
            ]
        return []

    @classmethod
    def _default_branch(cls, cfg: RouterConfig) -> str:
        return cfg.default or (cfg.branches[0].name if cfg.branches else "")

    @classmethod
    def compile(cls, cfg: RouterConfig, ctx: NodeContext) -> NodeFn:
        if cfg.kind == "rules":

            async def _passthrough(state: dict[str, Any]) -> dict[str, Any]:
                return {}

            return _passthrough

        # llm: classify the latest input into a branch, written to route_channel.
        model = model_for_node(ctx, cfg.model)
        default = cls._default_branch(cfg)

        async def _classify(state: dict[str, Any]) -> dict[str, Any]:
            query = _last_text(state.get(cfg.input_channel))
            reply = await collect_text(
                model,
                model_id=cfg.model,
                system=_classify_prompt(cfg),
                messages=[Msg(role=Role.user, content=query)],
                temperature=0.0,
            )
            return {cfg.route_channel: _pick_branch(reply, cfg, default)}

        return _classify

    @classmethod
    def routing(
        cls, cfg: RouterConfig, ctx: NodeContext
    ) -> Callable[[dict[str, Any]], str]:
        default = cls._default_branch(cfg)
        if cfg.kind == "rules":
            if not custom_code_allowed():
                raise PermissionError(
                    "Router rules use eval; set CALYPR_ALLOW_CUSTOM_CODE=1 in a trusted env."
                )
            branches = list(cfg.branches)

            def _route(state: dict[str, Any]) -> str:
                for b in branches:
                    if b.when and _eval_rule(b.when, state):
                        return b.name
                return default

            return _route

        # llm: read the branch the node body classified into.
        def _route_llm(state: dict[str, Any]) -> str:
            return state.get(cfg.route_channel) or default

        return _route_llm

    @classmethod
    def codegen(cls, cfg: RouterConfig, fn_name: str, ctx=None) -> CodeFragment:
        default = cls._default_branch(cfg)
        if cfg.kind == "llm":
            return cls._codegen_llm(cfg, fn_name, default)

        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """If-Else router — passthrough; routing is on the conditional edges."""',
            "    return {}",
            "",
            "",
            f"def route_{fn_name}(state: State) -> str:",
            '    """Pick the branch for the If-Else node."""',
        ]
        for b in cfg.branches:
            if b.when:
                lines.append(f"    if {b.when}:")
                lines.append(f"        return {json.dumps(b.name)}")
        lines.append(f"    return {json.dumps(default)}")
        return CodeFragment(
            fn_name=fn_name, function="\n".join(lines) + "\n", routing=True
        )

    @classmethod
    def _codegen_llm(cls, cfg: RouterConfig, fn_name: str, default: str) -> CodeFragment:
        names = [b.name for b in cfg.branches]
        imports = [
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import HumanMessage, SystemMessage",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Routing classifier: pick a branch for the latest request."""',
            f"    model = init_chat_model({cfg.model!r}, temperature=0.0)",
            f'    messages = state.get("{cfg.input_channel}") or []',
            '    query = messages[-1].content if messages else ""',
            *assign_str("system", _classify_prompt(cfg)),
            "    reply = model.invoke(",
            "        [SystemMessage(content=system), HumanMessage(content=query)]",
            "    ).content.lower()",
            f"    options = {names!r}",
            f"    choice = next((o for o in options if o.lower() in reply), {default!r})",
            f'    return {{"{cfg.route_channel}": choice}}',
            "",
            "",
            f"def route_{fn_name}(state: State) -> str:",
            '    """Pick the branch chosen by the classifier."""',
            f'    return state.get("{cfg.route_channel}", {default!r})',
        ]
        return CodeFragment(
            fn_name=fn_name,
            function="\n".join(lines) + "\n",
            imports=imports,
            routing=True,
        )
