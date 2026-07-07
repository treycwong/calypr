"""The keyless FakeAssistant: keyword routing + a full, valid event sequence."""

from __future__ import annotations

from calypr_assistant import FakeAssistant
from calypr_assistant.events import Graph, Note, Status, Usage
from calypr_compiler import validate_graph


async def _collect(prompt: str) -> list:
    return [ev async for ev in FakeAssistant().draft([{"role": "user", "content": prompt}])]


async def test_rag_keyword_maps_to_a_retriever_graph() -> None:
    events = await _collect("I would like a RAG chatbot for my website")
    graph = next(e for e in events if isinstance(e, Graph))
    assert any(n.type == "retriever" for n in graph.spec.nodes)
    assert not [i for i in validate_graph(graph.spec) if i.severity == "error"]


async def test_route_keyword_maps_to_a_router_graph() -> None:
    events = await _collect("classify and translate incoming messages")
    graph = next(e for e in events if isinstance(e, Graph))
    assert any(n.type == "router" for n in graph.spec.nodes)


async def test_fallback_is_the_golden_graph() -> None:
    events = await _collect("just something simple")
    graph = next(e for e in events if isinstance(e, Graph))
    types = sorted(n.type for n in graph.spec.nodes)
    assert types == ["agent", "input", "output"]


async def test_llm_nodes_forced_to_fake_model() -> None:
    # The fake path is keyless, so generated graphs must run without a provider key.
    events = await _collect("rag over my docs")
    graph = next(e for e in events if isinstance(e, Graph))
    models = [n.config["model"] for n in graph.spec.nodes if "model" in n.config]
    assert models and all(m == "fake" for m in models)


async def test_full_event_sequence_and_validity() -> None:
    events = await _collect("rag over my docs")
    assert any(isinstance(e, Status) for e in events)
    assert any(isinstance(e, Usage) for e in events)
    assert any(isinstance(e, Note) for e in events)
    graph = next(e for e in events if isinstance(e, Graph))
    # normalized like the real path
    assert all(n.position is None for n in graph.spec.nodes)
    assert not [i for i in validate_graph(graph.spec) if i.severity == "error"]
