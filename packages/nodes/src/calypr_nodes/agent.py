"""Agent node — the hero (CLAUDE-PLAN.md §3). A model + system prompt + (later) tools,
exposed as a small ladder of agent *types* (Russell & Norvig): simple-reflex (reacts),
model-based (remembers), goal-based (aims), utility-based (evaluates), learning (adapts),
and reflection (self-critiques). The type is a preset: it scaffolds the system prompt and,
for reflection/utility, runs a small internal loop. Each type emits matching idiomatic
Python in `codegen()`, so the round-trip holds (Phase 4).

Tools + RAG land in Phase 5; goal-based and utility-based reach full power there. Until
then they run as single-or-looped model calls with type-specific framing."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from calypr_model import Done, Msg, Role, TextDelta, ToolCall, Usage
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._convert import lc_to_msgs, render_template, safe_stream_writer
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    CodegenContext,
    NodeContext,
    NodeFn,
    NodeMeta,
    model_for_node,
    register,
)


def _to_lc_tool_calls(calls: list[ToolCall]) -> list[dict]:
    return [{"id": tc.id, "name": tc.name, "args": tc.args} for tc in calls]


# `{{ state.x }}` prompt placeholders — render_template substitutes these at runtime; codegen
# emits the equivalent so the *generated* agent fills them in too (e.g. retrieved context).
_PLACEHOLDER = re.compile(r"{{\s*state\.([A-Za-z_]\w*)\s*}}")


def _placeholders(text: str) -> list[tuple[str, str]]:
    """Unique (exact placeholder, channel) pairs in `text`, in first-seen order."""
    seen: dict[str, str] = {}
    for m in _PLACEHOLDER.finditer(text):
        seen.setdefault(m.group(0), m.group(1))
    return list(seen.items())

AgentType = Literal[
    "simple_reflex",
    "model_based",
    "goal_based",
    "utility_based",
    "learning",
    "reflection",
]

# Type-specific system-prompt framing — the cheapest, highest-leverage differentiator.
_SCAFFOLD: dict[str, str] = {
    "simple_reflex": (
        "You are a reactive agent. Respond to the current input directly, without "
        "relying on prior conversation."
    ),
    "model_based": "You track the conversation state and use it to inform each response.",
    "goal_based": (
        "You are a goal-directed agent. Plan the steps required, then act toward the goal."
    ),
    "utility_based": (
        "You optimise for quality. Aim for the most complete, accurate, and helpful answer."
    ),
    "learning": (
        "You adapt from feedback in the conversation, improving your answers over time."
    ),
    "reflection": (
        "You answer, then critically review and revise your own answer before finalising."
    ),
}

_DOC: dict[str, str] = {
    "simple_reflex": "Simple reflex agent: respond to the latest input only.",
    "model_based": "Model-based agent: respond using the full conversation state.",
    "goal_based": "Goal-based agent: plan toward the goal, then act.",
    "utility_based": "Utility-based agent: generate candidates and keep the best.",
    "learning": "Learning agent: adapt from feedback in the conversation.",
    "reflection": "Reflection agent: answer, then critique and revise.",
}


class AgentConfig(BaseModel):
    agent_type: AgentType = "model_based"
    # Model id is resolved against the provider at runtime; the fake client ignores it.
    model: str = "claude-sonnet-4-5"
    system_prompt: str = ""
    input_channel: str = "messages"
    output_channel: str = "messages"
    temperature: float = 0.7
    max_tokens: int = 1024
    max_steps: int = 8  # tool-loop cap (a cost guard; tools land in Phase 5)
    # goal-based
    goal: str = ""
    # reflection
    max_reflections: int = 2
    reflection_criteria: str = "accuracy, clarity, and completeness"
    # utility-based
    num_candidates: int = 3
    utility_criteria: str = "the most complete, accurate, and helpful answer"


def _scaffold(cfg: AgentConfig, base: str) -> str:
    """Prepend the type's framing to the user's system prompt."""
    framing = _SCAFFOLD.get(cfg.agent_type, "")
    if cfg.agent_type == "goal_based" and cfg.goal:
        framing = f"{framing} Goal: {cfg.goal}"
    return "\n\n".join(p for p in (framing, base) if p)


def _critique_prompt(cfg: AgentConfig) -> str:
    return (
        f"Critique the assistant's latest answer for {cfg.reflection_criteria}. "
        "List concrete, actionable fixes. If it is already excellent, reply 'OK'."
    )


def _latest_user_turn(history: list[Msg]) -> list[Msg]:
    """Simple-reflex sees only the most recent user input (no memory)."""
    for m in reversed(history):
        if m.role == Role.user:
            return [m]
    return history[-1:] if history else []


def _silent(_payload: dict) -> None:
    """A no-op stream writer for internal (critique / extra-candidate) calls."""
    return None


@register
class AgentNode(BaseNode):
    type = "agent"
    meta = NodeMeta(
        label="Agent",
        category="reasoning",
        icon="bot",
        description="A model with a selectable agent type — a complete agent on its own.",
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
        model = model_for_node(ctx, cfg.model)  # each agent uses its own provider
        tool_schemas = ctx.tools or []  # bound by the compiler from wired Tool nodes

        async def _call(
            system: str, messages: list[Msg], writer
        ) -> tuple[str, list[ToolCall]]:
            """One streaming model call; returns the final text + any tool calls."""
            text = ""
            calls: list[ToolCall] = []
            async for ev in model.stream(
                model=cfg.model,
                system=system,
                messages=messages,
                tools=tool_schemas,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            ):
                if isinstance(ev, TextDelta):
                    writer({"type": "token", "text": ev.text})
                elif isinstance(ev, ToolCall):
                    calls.append(ev)
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
                    calls = ev.tool_calls or calls
            return text, calls

        async def _reflect(system: str, history: list[Msg], writer) -> str:
            """Generate, then critique → revise up to `max_reflections` times. Only the
            final revision streams to the playground; the loop is bounded (terminates)."""
            n = max(0, cfg.max_reflections)
            reply, _ = await _call(system, history, _silent if n else writer)
            for i in range(n):
                critique, _ = await _call(
                    _critique_prompt(cfg),
                    [Msg(role=Role.user, content=reply)],
                    _silent,
                )
                revise_system = (
                    f"{system}\n\nA reviewer noted:\n{critique}\n\n"
                    "Revise your previous answer to address it."
                ).strip()
                reply, _ = await _call(
                    revise_system,
                    [*history, Msg(role=Role.assistant, content=reply)],
                    writer if i == n - 1 else _silent,
                )
            return reply

        async def _utility(system: str, history: list[Msg], writer) -> str:
            """Generate `num_candidates` and keep the strongest (most thorough). A visible
            version composes an Evaluator + Router; this internal preset is best-of-N."""
            candidates: list[str] = []
            n = max(1, cfg.num_candidates)
            for i in range(n):
                text, _ = await _call(system, history, writer if i == 0 else _silent)
                candidates.append(text)
            return max(candidates, key=len)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            writer = safe_stream_writer()
            system = _scaffold(cfg, render_template(cfg.system_prompt, state))
            history: list[Msg] = lc_to_msgs(state.get(cfg.input_channel) or [])
            if cfg.agent_type == "simple_reflex":
                history = _latest_user_turn(history)

            if cfg.agent_type == "reflection":
                message = AIMessage(content=await _reflect(system, history, writer))
            elif cfg.agent_type == "utility_based":
                message = AIMessage(content=await _utility(system, history, writer))
            else:
                reply, calls = await _call(system, history, writer)
                # Preserve tool calls so a wired Tool node + conditional edge can act (ReAct).
                message = AIMessage(
                    content=reply, tool_calls=_to_lc_tool_calls(calls)
                )

            return {cfg.output_channel: [message]}

        return _run

    @classmethod
    def routing(cls, cfg: AgentConfig, ctx: NodeContext):
        """With tools bound, the agent branches like LangGraph's `tools_condition`: if its
        last message asked for a tool, take the `tools` branch (→ a Tool node that loops
        back); otherwise `respond` (→ the finish edge). Without tools, a plain node."""
        if not ctx.tools:
            return None
        out = cfg.output_channel

        def _route(state: dict[str, Any]) -> str:
            messages = state.get(out) or []
            last = messages[-1] if messages else None
            return "tools" if getattr(last, "tool_calls", None) else "respond"

        return _route

    @classmethod
    def codegen(
        cls, cfg: AgentConfig, fn_name: str, ctx: CodegenContext | None = None
    ) -> CodeFragment:
        imports = ["from langchain.chat_models import init_chat_model"]
        system = _scaffold(cfg, cfg.system_prompt)
        msg_imports: set[str] = {"SystemMessage"} if system else set()
        out = cfg.output_channel

        model_expr = f"init_chat_model({json.dumps(cfg.model)}, temperature={cfg.temperature})"
        tool_refs = ctx.tool_refs if ctx else []
        if tool_refs:
            model_expr += f".bind_tools([{', '.join(tool_refs)}])"

        head = [
            f"def {fn_name}(state: State) -> dict:",
            f'    """{_DOC[cfg.agent_type]}"""',
            f"    model = {model_expr}",
            f'    messages = state.get("{cfg.input_channel}") or []',
        ]
        if system:
            head.extend(assign_str("system", system))
            # `{{ state.x }}` placeholders fill from state at runtime, mirroring render_template.
            for placeholder, channel in _placeholders(system):
                head.append(
                    f"    system = system.replace({placeholder!r}, "
                    f'str(state.get({channel!r}, "")))'
                )

        prompt = "[SystemMessage(content=system), *messages]" if system else "messages"

        if cfg.agent_type == "simple_reflex":
            msg_imports.add("HumanMessage")
            latest = (
                "[SystemMessage(content=system), *latest]" if system else "latest"
            )
            body = [
                "    latest = [m for m in messages if isinstance(m, HumanMessage)][-1:]",
                f"    reply = model.invoke({latest})",
                f'    return {{"{out}": [reply]}}',
            ]
        elif cfg.agent_type == "utility_based":
            msg_imports.add("AIMessage")
            body = [
                f"    prompt = {prompt}",
                "    candidates = [",
                f"        model.invoke(prompt).content for _ in range({cfg.num_candidates})",
                "    ]",
                "    best = max(candidates, key=len)",
                f'    return {{"{out}": [AIMessage(content=best)]}}',
            ]
        elif cfg.agent_type == "reflection":
            msg_imports.update({"AIMessage", "HumanMessage"})
            base_sys = "system" if system else '""'
            body = [
                *assign_str("critique_prompt", _critique_prompt(cfg)),
                f"    reply = model.invoke({prompt}).content",
                f"    for _ in range({max(0, cfg.max_reflections)}):",
                "        critique = model.invoke(",
                "            [",
                "                SystemMessage(content=critique_prompt),",
                "                HumanMessage(content=reply),",
                "            ]",
                "        ).content",
                f"        revise_system = {base_sys} + "
                '"\\n\\nA reviewer noted:\\n" + critique',
                "        reply = model.invoke(",
                "            [",
                "                SystemMessage(content=revise_system),",
                "                *messages,",
                "                AIMessage(content=reply),",
                "            ]",
                "        ).content",
                f'    return {{"{out}": [AIMessage(content=reply)]}}',
            ]
        else:  # model_based, goal_based, learning — single call over full state
            body = [
                f"    reply = model.invoke({prompt})",
                f'    return {{"{out}": [reply]}}',
            ]

        if msg_imports:
            imports.append(
                "from langchain_core.messages import " + ", ".join(sorted(msg_imports))
            )
        return CodeFragment(
            fn_name=fn_name, function="\n".join(head + body) + "\n", imports=imports
        )
