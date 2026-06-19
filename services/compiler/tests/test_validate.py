from calypr_compiler import validate_graph
from calypr_compiler.golden import input_agent_output
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel


def _codes(spec) -> set[str]:
    return {i.code for i in validate_graph(spec)}


def test_golden_spec_has_no_errors():
    errors = [i for i in validate_graph(input_agent_output()) if i.severity == "error"]
    assert errors == []


def test_missing_output_bad_entry_and_dead_end():
    spec = GraphSpec(
        id="x",
        name="x",
        state=[StateChannel(key="messages", type="messages", reducer=Reducer.append)],
        nodes=[NodeSpec(id="in", type="input", config={})],
        edges=[],
        entry="nope",
    )
    codes = _codes(spec)
    assert {"no_output", "bad_entry", "dead_end"} <= codes


def test_dangling_edge_and_unknown_node_type():
    spec = GraphSpec(
        id="x",
        name="x",
        state=[StateChannel(key="output", type="string", reducer=Reducer.last)],
        nodes=[
            NodeSpec(id="out", type="output", config={}),
            NodeSpec(id="z", type="mystery", config={}),
        ],
        edges=[EdgeSpec(id="e", source="z", target="ghost")],
        entry="z",
    )
    codes = _codes(spec)
    assert {"unknown_node_type", "dangling_edge"} <= codes
