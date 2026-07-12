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


def test_unconditional_back_edge_is_a_cyclic_error():
    # A plain back-edge into the agent (Input→Agent→Output→Agent) loops forever — the run
    # would repeat to the recursion limit. It must be caught before compiling/running.
    spec = input_agent_output()
    agent = next(n.id for n in spec.nodes if n.type == "agent")
    out = next(n.id for n in spec.nodes if n.type == "output")
    spec.edges.append(EdgeSpec(id="cycle", source=out, target=agent))
    assert "cyclic_graph" in _codes(spec)


def test_self_loop_is_a_cyclic_error():
    spec = input_agent_output()
    agent = next(n.id for n in spec.nodes if n.type == "agent")
    spec.edges.append(EdgeSpec(id="self", source=agent, target=agent))
    assert "cyclic_graph" in _codes(spec)


def test_conditional_back_edge_is_not_flagged():
    # A loop whose return path is a *conditional* edge (like a ReAct tools_condition or a
    # Router) can exit, so the infinite-loop guard must not trip on it.
    spec = input_agent_output()
    agent = next(n.id for n in spec.nodes if n.type == "agent")
    out = next(n.id for n in spec.nodes if n.type == "output")
    spec.edges.append(EdgeSpec(id="cond", source=out, target=agent, condition="again"))
    assert "cyclic_graph" not in _codes(spec)


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
