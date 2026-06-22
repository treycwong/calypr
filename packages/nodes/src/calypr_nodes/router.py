"""Router / If-Else node — conditional control flow (Phase 4 keystone).

The node is a passthrough; the *decision* is `routing()`, which the compiler wires via
`add_conditional_edges` to the targets of this node's labelled out-edges (the edge's
`condition` is the branch name). Rule predicates are small Python expressions over
`state`, gated behind the same trusted flag as Custom Code (they use `eval`). An LLM
classifier kind is filled in with the agent presets."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from calypr_nodes.code import custom_code_allowed
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
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


class Branch(BaseModel):
    name: str  # must match an outgoing edge's `condition`
    when: str = ""  # a Python expression over `state`, e.g. '"refund" in state["input"]'


class RouterConfig(BaseModel):
    kind: Literal["rules", "llm"] = "rules"
    input_channel: str = "messages"
    branches: list[Branch] = []
    default: str = ""  # branch name to use when none match


@register
class RouterNode(BaseNode):
    type = "router"
    meta = NodeMeta(
        label="If-Else",
        category="control",
        icon="git-branch",
        description="Branch the flow on a condition (rules now; LLM classifier soon).",
    )
    config_model = RouterConfig

    @classmethod
    def reads(cls, cfg: RouterConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: RouterConfig) -> list[str]:
        return []

    @classmethod
    def _default_branch(cls, cfg: RouterConfig) -> str:
        return cfg.default or (cfg.branches[0].name if cfg.branches else "")

    @classmethod
    def compile(cls, cfg: RouterConfig, ctx: NodeContext) -> NodeFn:
        async def _passthrough(state: dict[str, Any]) -> dict[str, Any]:
            return {}

        return _passthrough

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

        # llm classifier kind is implemented with the agent presets (Task 22).
        def _route_default(state: dict[str, Any]) -> str:
            return default

        return _route_default

    @classmethod
    def codegen(cls, cfg: RouterConfig, fn_name: str, ctx=None) -> CodeFragment:
        default = cls._default_branch(cfg)
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
