"""Evaluator / Scorer node — LLM-as-judge (Phase 4 capability node).

Scores the latest answer on a `criteria` rubric (1..`scale_max`) and writes the numeric
score + a short rationale to state. It powers utility-based selection, reflection critique,
and the wedge's eval/trust layer — and pairs with a Router to branch on quality (e.g.
"score < 7 → revise"). Single model call; tools/RAG arrive in Phase 5."""

from __future__ import annotations

import re
from typing import Any

from calypr_model import Msg, Role
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._llm import collect_text
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)

_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


class EvaluatorConfig(BaseModel):
    model: str = "claude-sonnet-4-5"
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
    def compile(cls, cfg: EvaluatorConfig, ctx: NodeContext) -> NodeFn:
        if ctx.model is None:
            raise ValueError("Evaluator node requires a model client in NodeContext")
        model = ctx.model

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            answer = _last_text(state.get(cfg.input_channel))
            text = await collect_text(
                model,
                model_id=cfg.model,
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
    def codegen(cls, cfg: EvaluatorConfig, fn_name: str) -> CodeFragment:
        imports = [
            "import re",
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import HumanMessage, SystemMessage",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """LLM-as-judge: score the latest answer and explain why."""',
            f"    model = init_chat_model({cfg.model!r}, temperature={cfg.temperature})",
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
