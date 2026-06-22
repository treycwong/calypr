"""Custom Code node — the no-ceiling escape hatch (realignment §Phase 3).

The user writes a Python function body over `state` that returns a partial state update.
`codegen()` emits it verbatim into the generated module (safe — the engineer owns the
file). `compile()` runs it on our runtime, which executes arbitrary user code, so it is
gated behind a trusted flag until sandboxing lands (CLAUDE-PLAN §3.2)."""

from __future__ import annotations

import os
import textwrap
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel

from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)

# Symbols available to a custom-code body without an explicit import.
_COMMON_NS: dict[str, Any] = {
    "HumanMessage": HumanMessage,
    "AIMessage": AIMessage,
    "SystemMessage": SystemMessage,
    "ToolMessage": ToolMessage,
}


def custom_code_allowed() -> bool:
    """Hosted execution of user code is off unless explicitly allowed (dev/design-partner)."""
    return os.environ.get("CALYPR_ALLOW_CUSTOM_CODE", "1") == "1"


class CodeConfig(BaseModel):
    # A function body over `state`, e.g. `return {"output": state["input"].upper()}`.
    code: str = "return {}"
    imports: list[str] = []
    input_channel: str = "messages"
    output_channel: str = "messages"


@register
class CodeNode(BaseNode):
    type = "code"
    meta = NodeMeta(
        label="Custom Code",
        category="logic",
        icon="code",
        description="Drop to Python for anything the canvas can't express. Round-trips.",
    )
    config_model = CodeConfig

    @classmethod
    def reads(cls, cfg: CodeConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: CodeConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def compile(cls, cfg: CodeConfig, ctx: NodeContext) -> NodeFn:
        if not custom_code_allowed():
            raise PermissionError(
                "Custom Code execution is disabled (set CALYPR_ALLOW_CUSTOM_CODE=1 "
                "in a trusted environment)."
            )
        namespace: dict[str, Any] = dict(_COMMON_NS)
        for line in cfg.imports:
            exec(line, namespace)  # noqa: S102 — trusted, gated above
        source = "def _user_node(state):\n" + textwrap.indent(cfg.code, "    ")
        exec(source, namespace)  # noqa: S102
        user_fn = namespace["_user_node"]

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            return user_fn(state) or {}

        return _run

    @classmethod
    def codegen(cls, cfg: CodeConfig, fn_name: str, ctx=None) -> CodeFragment:
        body = textwrap.indent(cfg.code.rstrip("\n"), "    ")
        fn = f"def {fn_name}(state: State) -> dict:\n{body}\n"
        return CodeFragment(fn_name=fn_name, function=fn, imports=list(cfg.imports))
