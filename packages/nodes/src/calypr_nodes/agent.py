"""Agent node — the hero (CLAUDE-PLAN.md §3). A model + system prompt + (later) tools
and knowledge bases, run as a tool loop. One Agent node is a complete E2E agent.

Phase 1 wires the loop end-to-end with no tools attached, so it resolves in a single
model call. The loop structure is in place for Phase 3 (tool execution + iteration)."""

from __future__ import annotations

from typing import Any

from calypr_model import Done, Msg, Role, TextDelta, ToolCall, ToolCallRequest, Usage
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from calypr_nodes._convert import lc_to_msgs, render_template, safe_stream_writer
from calypr_nodes.registry import BaseNode, NodeContext, NodeFn, NodeMeta, register


class AgentConfig(BaseModel):
    # Model id is resolved against the provider at runtime; the fake client ignores it.
    model: str = "claude-sonnet-4-5"
    system_prompt: str = ""
    input_channel: str = "messages"
    output_channel: str = "messages"
    temperature: float = 0.7
    max_tokens: int = 1024
    max_steps: int = 8  # tool-loop cap (a cost guard, on by default)


def _to_lc_tool_calls(tool_calls: list[ToolCall]) -> list[dict]:
    return [{"id": tc.id, "name": tc.name, "args": tc.args} for tc in tool_calls]


@register
class AgentNode(BaseNode):
    type = "agent"
    meta = NodeMeta(
        label="Agent",
        category="reasoning",
        icon="bot",
        description="A model with a tool loop — a complete agent on its own.",
    )
    config_model = AgentConfig

    @classmethod
    def reads(cls, cfg: AgentConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: AgentConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def compile(cls, cfg: AgentConfig, ctx: NodeContext) -> NodeFn:
        if ctx.model is None:
            raise ValueError("Agent node requires a model client in NodeContext")
        model = ctx.model

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            writer = safe_stream_writer()
            system = render_template(cfg.system_prompt, state)
            history: list[Msg] = lc_to_msgs(state.get(cfg.input_channel) or [])
            produced: list[AIMessage] = []

            for _step in range(cfg.max_steps):
                text = ""
                tool_calls: list[ToolCall] = []
                async for ev in model.stream(
                    model=cfg.model,
                    system=system,
                    messages=history,
                    tools=[],  # Phase 1: no tools attached yet (Phase 3)
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                ):
                    if isinstance(ev, TextDelta):
                        writer({"type": "token", "text": ev.text})
                    elif isinstance(ev, ToolCall):
                        tool_calls.append(ev)
                    elif isinstance(ev, Usage):
                        writer(
                            {
                                "type": "usage",
                                "input_tokens": ev.input_tokens,
                                "output_tokens": ev.output_tokens,
                            }
                        )
                    elif isinstance(ev, Done):
                        text = ev.text
                        tool_calls = ev.tool_calls or tool_calls

                produced.append(
                    AIMessage(content=text, tool_calls=_to_lc_tool_calls(tool_calls))
                )
                history.append(
                    Msg(
                        role=Role.assistant,
                        content=text,
                        tool_calls=[
                            ToolCallRequest(tc.id, tc.name, tc.args) for tc in tool_calls
                        ],
                    )
                )

                # Phase 3 will execute tool_calls here (append tool results, continue).
                # With no tool registry yet, we always stop after one turn.
                break

            return {cfg.output_channel: produced}

        return _run
