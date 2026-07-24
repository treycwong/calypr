"""Agent node — the hero (CLAUDE-PLAN.md §3). A model + system prompt + (later) tools,
exposed as a small ladder of agent *types* (Russell & Norvig): simple-reflex (reacts),
model-based (remembers), goal-based (aims), utility-based (evaluates), learning (adapts),
and reflection (self-critiques). The type is a preset: it scaffolds the system prompt and,
for reflection/utility, runs a small internal loop. Each type emits matching idiomatic
Python in `codegen()`, so the round-trip holds (Phase 4).

Tools + RAG land in Phase 5; goal-based and utility-based reach full power there. Until
then they run as single-or-looped model calls with type-specific framing."""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Literal

from calypr_model import Done, Msg, Role, TextDelta, ToolCall, Usage
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import lc_to_msgs, render_template, safe_stream_writer
from calypr_nodes._parse import (
    calls_named,
    docstring,
    return_dict_key,
    state_get_keys,
    str_const,
)
from calypr_nodes.registry import (
    PLATFORM_DEFAULT_MODEL,
    BaseNode,
    CodeFragment,
    CodegenContext,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    effective_model,
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
    "learning": ("You adapt from feedback in the conversation, improving your answers over time."),
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


# Reverse of `_DOC` — the docstring the generator emits is a unique, stable marker of the
# agent *type*, so it's the recogniser's primary discriminator (and separates an Agent from a
# Router, whose docstrings live elsewhere).
_DOC_REVERSE: dict[str, str] = {doc: agent_type for agent_type, doc in _DOC.items()}

_CRITIQUE_PREFIX = "Critique the assistant's latest answer for "
_CRITIQUE_SUFFIX = ". List concrete, actionable fixes. If it is already excellent, reply 'OK'."


def _string_assign(fn: ast.FunctionDef, name: str) -> str | None:
    """The value of the first `name = "<literal>"` assignment in the function (implicit string
    concatenation is already joined by the parser, so a wrapped literal reads back whole)."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and (value := str_const(node.value)) is not None
        ):
            return value
    return None


def _recover_prompt(agent_type: str, system: str) -> tuple[str, str]:
    """Undo `_scaffold`: split the emitted `system` string back into (system_prompt, goal).

    The generator prepends type framing (`_SCAFFOLD`), plus ` Goal: <goal>` for a goal-based
    agent, joined to the user prompt by a blank line. Recovery only has to be *codegen-exact*:
    re-scaffolding the returned (prompt, goal) must reproduce `system` — so where the blank-line
    split falls inside the prompt is irrelevant (it's all concatenation)."""
    framing = _SCAFFOLD.get(agent_type, "")
    if not framing or not system.startswith(framing):
        return system, ""  # framing edited/absent — treat the whole thing as the prompt
    rest = system[len(framing) :]
    if agent_type == "goal_based" and rest.startswith(" Goal: "):
        goal, _, base = rest[len(" Goal: ") :].partition("\n\n")
        return base, goal
    base = rest[2:] if rest.startswith("\n\n") else rest  # rest is "" or "\n\n" + prompt
    return base, ""


def _first_range_int(fn: ast.FunctionDef) -> int | None:
    """The integer argument of the function's first `range(<n>)` call (the reflection loop
    bound / utility candidate count the generator emits as a literal)."""
    for call in calls_named(fn, "range"):
        if call.args and isinstance(call.args[0], ast.Constant):
            value = call.args[0].value
            if isinstance(value, int):
                return value
    return None


class AgentConfig(BaseModel):
    agent_type: AgentType = "model_based"
    # Model id is resolved against the provider at runtime; the fake client ignores it.
    #: Empty = inherit (workspace default → PLATFORM_DEFAULT_MODEL). See `effective_model`.
    model: str = ""
    system_prompt: str = ""
    # Optional display name on the canvas (e.g. "Orchestrator", "Flights"). Cosmetic only —
    # the engine + codegen ignore it; it distinguishes role-specialized agents in the UI.
    label: str = ""
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
        model_id = effective_model(ctx, cfg.model)
        model = model_for_node(ctx, cfg.model)  # each agent uses its own provider
        tool_schemas = ctx.tools or []  # bound by the compiler from wired Tool nodes

        async def _call(system: str, messages: list[Msg], writer) -> tuple[str, list[ToolCall]]:
            """One streaming model call; returns the final text + any tool calls."""
            text = ""
            calls: list[ToolCall] = []
            async for ev in model.stream(
                model=model_id,
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
                            "node_id": current_node_id.get(None),
                            # The *resolved* id, not `cfg.model` — this node's config defaults to
                            # "" (inherit), and an empty id is priced at `pricing`'s fail-closed
                            # most-expensive rate. In production that billed ordinary gpt-4o-mini
                            # traffic at ~163× its real cost and accounted for over half of all
                            # recorded platform spend. Harmless while nothing read the number;
                            # once credits are enforced it over-debits real customers.
                            "model": model_id,
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
                message = AIMessage(content=reply, tool_calls=_to_lc_tool_calls(calls))

            return {cfg.output_channel: [message]}

        return _run

    @classmethod
    def routing(cls, cfg: AgentConfig, ctx: NodeContext):
        """With tools bound, the agent branches like LangGraph's `tools_condition`: if its
        last message asked for a tool, take the `tools` branch (→ a Tool node that loops
        back); otherwise `respond` (→ the finish edge). Without tools, a plain node.

        `ctx.tools is None` means the agent has no wired Tool node at all → plain node. An
        empty list means it *is* wired to a Tool node that currently exposes zero tools (e.g.
        an unconfigured MCP server) — still install the router so it routes `respond` and
        terminates, rather than letting the ReAct edges collapse into an infinite loop.

        With *several* Tool nodes wired (say Notion and web search), `tools` is ambiguous —
        every such edge carries the same branch name, so a single `tools` branch can only ever
        reach one of them while the agent binds all of their tools. `ctx.tool_owners` resolves
        the call by name to its owning node id instead, and a turn that calls tools from two
        different nodes fans out to both (each Tool node answers only its own calls)."""
        if ctx.tools is None:
            return None
        out = cfg.output_channel
        owners = ctx.tool_owners

        def _route(state: dict[str, Any]) -> str | list[str]:
            messages = state.get(out) or []
            last = messages[-1] if messages else None
            calls = getattr(last, "tool_calls", None)
            if not calls:
                return "respond"
            if not owners:
                return "tools"
            # dict.fromkeys: dedupe (two calls to one node visit it once) but keep order, so
            # the branch taken is stable for a given turn rather than set-iteration order.
            targets = list(dict.fromkeys(o for c in calls if (o := owners.get(c.get("name")))))
            if not targets:
                return "tools"  # unknown tool name — let the wired node explain itself
            return targets if len(targets) > 1 else targets[0]

        return _route

    @classmethod
    def codegen(
        cls, cfg: AgentConfig, fn_name: str, ctx: CodegenContext | None = None
    ) -> CodeFragment:
        imports = ["from langchain.chat_models import init_chat_model"]
        system = _scaffold(cfg, cfg.system_prompt)
        msg_imports: set[str] = {"SystemMessage"} if system else set()
        out = cfg.output_channel

        model_expr = (
            f"init_chat_model({json.dumps(cfg.model or PLATFORM_DEFAULT_MODEL)}, "
            f"temperature={cfg.temperature})"
        )
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
                    f'    system = system.replace({placeholder!r}, str(state.get({channel!r}, "")))'
                )

        prompt = "[SystemMessage(content=system), *messages]" if system else "messages"

        if cfg.agent_type == "simple_reflex":
            msg_imports.add("HumanMessage")
            latest = "[SystemMessage(content=system), *latest]" if system else "latest"
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
                f'        revise_system = {base_sys} + "\\n\\nA reviewer noted:\\n" + critique',
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
            imports.append("from langchain_core.messages import " + ", ".join(sorted(msg_imports)))
        return CodeFragment(
            fn_name=fn_name, function="\n".join(head + body) + "\n", imports=imports
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> AgentConfig | None:
        """Recover an Agent node from its generated function.

        The type-specific docstring is the discriminator; `init_chat_model(...)` yields the
        model + temperature; the `messages = state.get(...)` read and final return give the
        I/O channels; the `system = "..."` literal (minus the type scaffold) gives the prompt.
        Reflection/utility loop bounds and the critique criteria are read from the literals the
        generator emitted for those types. Fields the code never expresses (`max_tokens`,
        `max_steps`, cosmetic `label`, tool bindings — which come from wired edges, not config)
        fall back to defaults; that's codegen-lossless."""
        fn = ctx.func
        if fn is None:
            return None
        agent_type = _DOC_REVERSE.get(docstring(fn) or "")
        model_calls = calls_named(fn, "init_chat_model")
        if agent_type is None or not model_calls:
            return None  # not an Agent shape (or a Router — different docstring)

        call = model_calls[0]
        model = str_const(call.args[0]) if call.args else None
        temperature = next(
            (
                kw.value.value
                for kw in call.keywords
                if kw.arg == "temperature" and isinstance(kw.value, ast.Constant)
            ),
            None,
        )
        keys = state_get_keys(fn)
        output_channel = return_dict_key(fn)
        if model is None or temperature is None or not keys or output_channel is None:
            return None

        system_prompt, goal = "", ""
        raw_system = _string_assign(fn, "system")
        if raw_system is not None:
            system_prompt, goal = _recover_prompt(agent_type, raw_system)

        cfg = AgentConfig(
            agent_type=agent_type,
            model=model,
            temperature=float(temperature),
            system_prompt=system_prompt,
            input_channel=keys[0],
            output_channel=output_channel,
            goal=goal,
        )
        if agent_type == "reflection":
            n = _first_range_int(fn)
            if n is not None:
                cfg.max_reflections = n
            critique = _string_assign(fn, "critique_prompt") or ""
            if critique.startswith(_CRITIQUE_PREFIX) and critique.endswith(_CRITIQUE_SUFFIX):
                cfg.reflection_criteria = critique[len(_CRITIQUE_PREFIX) : -len(_CRITIQUE_SUFFIX)]
        elif agent_type == "utility_based":
            n = _first_range_int(fn)
            if n is not None:
                cfg.num_candidates = n
        return cfg
