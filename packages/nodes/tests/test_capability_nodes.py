"""Capability nodes: Evaluator (LLM-as-judge → score + rationale) and Memory
(buffer / summary). These compose with the Agent + Router to build the upper rungs of the
agent ladder (utility, reflection, learning)."""

from __future__ import annotations

from calypr_model import FakeModelClient
from calypr_nodes import EvaluatorConfig, MemoryConfig, NodeContext
from calypr_nodes.evaluator import EvaluatorNode
from calypr_nodes.memory import MemoryNode
from langchain_core.messages import AIMessage, HumanMessage


async def test_evaluator_parses_score_and_writes_rationale():
    ctx = NodeContext(model=FakeModelClient(reply="SCORE: 8\nClear and accurate."))
    run = EvaluatorNode.compile(EvaluatorConfig(model="x"), ctx)
    update = await run({"messages": [AIMessage(content="the answer")]})
    assert update["score"] == 8.0
    assert "Clear and accurate." in update["rationale"]


async def test_evaluator_clamps_to_scale_max():
    ctx = NodeContext(model=FakeModelClient(reply="SCORE: 99 — overshoots"))
    run = EvaluatorNode.compile(EvaluatorConfig(model="x", scale_max=10), ctx)
    update = await run({"messages": [AIMessage(content="x")]})
    assert update["score"] == 10.0


async def test_evaluator_falls_back_when_no_score():
    ctx = NodeContext(model=FakeModelClient(reply="I have opinions but no number."))
    run = EvaluatorNode.compile(EvaluatorConfig(model="x"), ctx)
    update = await run({"messages": [AIMessage(content="x")]})
    assert update["score"] == 0.0


async def test_memory_buffer_appends_latest_message():
    run = MemoryNode.compile(MemoryConfig(operation="buffer"), NodeContext())
    update = await run({"messages": [HumanMessage(content="remember this")]})
    assert update["memory"] == ["remember this"]  # append-reducer list channel


async def test_memory_summary_uses_the_model():
    ctx = NodeContext(model=FakeModelClient(reply="A concise summary."))
    run = MemoryNode.compile(MemoryConfig(operation="summary", model="x"), ctx)
    update = await run(
        {"messages": [HumanMessage(content="a"), AIMessage(content="b")]}
    )
    assert update["memory"] == ["A concise summary."]  # appended to the memory list
