import pytest
from calypr_compiler import CompileError, compile_graph
from calypr_compiler.golden import input_agent_output
from calypr_dsl import GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext


def _ctx() -> NodeContext:
    return NodeContext(model=FakeModelClient(reply="ok"))


def test_golden_compiles_with_expected_nodes_and_edges():
    compiled = compile_graph(input_agent_output(), _ctx())
    graph = compiled.get_graph()
    assert {"in", "agent", "out"} <= set(graph.nodes)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("in", "agent") in edges
    assert ("agent", "out") in edges


def test_compile_refuses_unknown_node_type():
    spec = GraphSpec(
        id="bad",
        name="bad",
        state=[StateChannel(key="output", type="string", reducer=Reducer.last)],
        nodes=[
            NodeSpec(id="out", type="output", config={}),
            NodeSpec(id="x", type="frobnicate", config={}),
        ],
        edges=[],
        entry="x",
    )
    with pytest.raises(CompileError) as exc:
        compile_graph(spec, _ctx())
    assert "unknown_node_type" in {i.code for i in exc.value.issues}
