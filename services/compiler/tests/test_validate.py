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


def _tool_graph(*edges: EdgeSpec) -> GraphSpec:
    """Input → Agent → (Router) → Tool, with the edges under test."""
    return GraphSpec(
        id="g",
        name="g",
        state=[
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(id="in", type="input", config={"target_channel": "messages"}),
            NodeSpec(id="agent", type="agent", config={"model": "fake"}),
            NodeSpec(
                id="router",
                type="router",
                config={
                    "kind": "llm",
                    "model": "fake",
                    "branches": [{"name": "notion", "when": "x"}, {"name": "respond", "when": "y"}],
                    "default": "respond",
                },
            ),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            NodeSpec(id="out", type="output", config={"source_channel": "messages"}),
        ],
        edges=list(edges),
        entry="in",
    )


def test_tool_node_wired_from_a_router_is_an_error():
    """The shape the assistant produced for "read my Notion": the Tool node hangs off a Router,
    so its schemas bind to a node that discards them and the model gets no tools at all. It
    used to compile and run, with the agent politely claiming it couldn't access Notion."""
    spec = _tool_graph(
        EdgeSpec(id="e1", source="in", target="agent"),
        EdgeSpec(id="e2", source="agent", target="router"),
        EdgeSpec(id="e3", source="router", target="tools", condition="notion"),
        EdgeSpec(id="e4", source="router", target="out", condition="respond"),
        EdgeSpec(id="e5", source="tools", target="out"),
    )
    codes = {i.code for i in validate_graph(spec) if i.severity == "error"}
    assert "tool_node_unbound" in codes


def test_tool_node_wired_from_the_agent_is_fine():
    spec = _tool_graph(
        EdgeSpec(id="e1", source="in", target="agent"),
        EdgeSpec(id="e2", source="agent", target="tools", condition="tools"),
        EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
        EdgeSpec(id="e4", source="tools", target="agent"),
    )
    codes = {i.code for i in validate_graph(spec) if i.severity == "error"}
    assert "tool_node_unbound" not in codes
