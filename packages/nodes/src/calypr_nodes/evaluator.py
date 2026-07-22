"""Evaluator / Scorer node — LLM-as-judge (Phase 4 capability node).

Scores the latest answer on a `criteria` rubric (1..`scale_max`) and writes the numeric
score + a short rationale to state. It powers utility-based selection, reflection critique,
and the wedge's eval/trust layer — and pairs with a Router to branch on quality (e.g.
"score < 7 → revise"). Single model call; tools/RAG arrive in Phase 5."""

from __future__ import annotations

import re
from typing import Any

from calypr_dsl import Reducer, StateChannel
from calypr_model import Msg, Role
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._llm import collect_text
from calypr_nodes._parse import (
    calls_named,
    docstring,
    kwarg_const,
    last_return_dict_items,
    state_get_keys,
    str_const,
    string_assign,
)
from calypr_nodes.registry import (
    PLATFORM_DEFAULT_MODEL,
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    effective_model,
    model_for_node,
    register,
)

_DOCSTRING = "LLM-as-judge: score the latest answer and explain why."
# Fixed spans of the emitted judge prompt (`_judge_prompt`) that bracket the recoverable
# `scale_max` and `criteria`: "... from 1 to {scale_max} on {criteria}. Reply with ...".
_JUDGE_MID = " on "
_JUDGE_SCALE_PREFIX = "Score the answer from 1 to "
_JUDGE_CRITERIA_SUFFIX = ". Reply with"

_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


class EvaluatorConfig(BaseModel):
    #: Empty = inherit (workspace default → PLATFORM_DEFAULT_MODEL). See `effective_model`.
    model: str = ""
    input_channel: str = "messages"  # the latest message here is what gets judged
    criteria: str = "accuracy, clarity, and completeness"
    scale_max: int = 10
    score_channel: str = "score"
    rationale_channel: str = "rationale"
    temperature: float = 0.0


def _last_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        last = value[-1]
        return getattr(last, "content", str(last))
    return ""


def _parse_score(text: str, scale_max: int) -> float:
    m = _SCORE_RE.search(text)
    if not m:
        return 0.0
    return max(0.0, min(float(scale_max), float(m.group(1))))


def _judge_prompt(cfg: EvaluatorConfig) -> str:
    return (
        f"You are a strict evaluator. Score the answer from 1 to {cfg.scale_max} on "
        f"{cfg.criteria}. Reply with 'SCORE: <number>' on the first line, then a one-line "
        "rationale."
    )


@register
class EvaluatorNode(BaseNode):
    type = "evaluator"
    meta = NodeMeta(
        label="Evaluator",
        category="control",
        icon="gauge",
        description="LLM-as-judge: score the answer on a rubric and explain why.",
    )
    config_model = EvaluatorConfig

    @classmethod
    def reads(cls, cfg: EvaluatorConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: EvaluatorConfig) -> list[str]:
        return [cfg.score_channel, cfg.rationale_channel]

    @classmethod
    def channels(cls, cfg: EvaluatorConfig) -> list[StateChannel]:
        return [
            StateChannel(key=cfg.score_channel, type="number", reducer=Reducer.last),
            StateChannel(key=cfg.rationale_channel, type="string", reducer=Reducer.last),
        ]

    @classmethod
    def compile(cls, cfg: EvaluatorConfig, ctx: NodeContext) -> NodeFn:
        model_id = effective_model(ctx, cfg.model)
        model = model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            answer = _last_text(state.get(cfg.input_channel))
            text = await collect_text(
                model,
                model_id=model_id,
                system=_judge_prompt(cfg),
                messages=[Msg(role=Role.user, content=answer)],
                temperature=cfg.temperature,
            )
            return {
                cfg.score_channel: _parse_score(text, cfg.scale_max),
                cfg.rationale_channel: text,
            }

        return _run

    @classmethod
    def codegen(cls, cfg: EvaluatorConfig, fn_name: str, ctx=None) -> CodeFragment:
        imports = [
            "import re",
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import HumanMessage, SystemMessage",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """LLM-as-judge: score the latest answer and explain why."""',
            f"    model = init_chat_model({(cfg.model or PLATFORM_DEFAULT_MODEL)!r}, "
            f"temperature={cfg.temperature})",
            f'    messages = state.get("{cfg.input_channel}") or []',
            '    answer = messages[-1].content if messages else ""',
            *assign_str("system", _judge_prompt(cfg)),
            "    result = model.invoke(",
            "        [SystemMessage(content=system), HumanMessage(content=answer)]",
            "    ).content",
            r'    match = re.search(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", result)',
            f"    score = min({float(cfg.scale_max)}, float(match.group(1))) "
            "if match else 0.0",
            f'    return {{"{cfg.score_channel}": score, '
            f'"{cfg.rationale_channel}": result}}',
        ]
        return CodeFragment(
            fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> EvaluatorConfig | None:
        """Recover an Evaluator (LLM-as-judge). Model + temperature come from
        `init_chat_model`; the two return keys are `(score_channel, rationale_channel)` in
        order; `scale_max` and `criteria` are read from the emitted judge prompt."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        calls = calls_named(fn, "init_chat_model")
        if not calls or not calls[0].args:
            return None
        model = str_const(calls[0].args[0])
        temperature = kwarg_const(calls[0], "temperature")
        keys = state_get_keys(fn)
        items = last_return_dict_items(fn)
        if model is None or not isinstance(temperature, (int, float)) or not keys or len(items) < 2:
            return None

        cfg = EvaluatorConfig(
            model=model,
            temperature=float(temperature),
            input_channel=keys[0],
            score_channel=items[0][0],
            rationale_channel=items[1][0],
        )
        system = string_assign(fn, "system") or ""
        if _JUDGE_SCALE_PREFIX in system and _JUDGE_MID in system:
            after = system.split(_JUDGE_SCALE_PREFIX, 1)[1]
            scale_str, _, rest = after.partition(_JUDGE_MID)
            if scale_str.isdigit():
                cfg.scale_max = int(scale_str)
            cfg.criteria = rest.split(_JUDGE_CRITERIA_SUFFIX, 1)[0]
        return cfg
