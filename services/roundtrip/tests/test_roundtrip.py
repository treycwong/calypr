"""Round-trip: `parse_python(generate_python(spec))` recovers every graph's nodes, edges, entry,
state channels, and (via the `# calypr:` trailer) identity + layout — for the golden builder and
all shipped starters.

The equivalence relation (modulo what the code can't express):

- **node ids**, **entry**, and edge **topology** (source → target) round-trip exactly;
- **state channels** round-trip by `(key, reducer, python-type)` — the forward type map is
  many-to-one (`string`/`str` → `str`), so equality is up to that canonicalisation; channel
  `default`s aren't emitted into a TypedDict, so they aren't compared;
- **identity** (`id`/`name`/`description`) and **layout** (node positions) round-trip via the
  `# calypr:` trailer; **without** the trailer parsing still succeeds — positions become None,
  the id falls back to `"parsed"`, and the name is read from the module docstring;
- **node type + config** round-trip via the Week-6 recognisers (`parse()` beside each node's
  `codegen()`): `generate ∘ parse ∘ generate` is a byte-identical fixed point for the corpus, and
  a function no recogniser matches degrades to a `code` node rather than being misclassified;
- **edge ids** are regenerated (not compared);
- **edge conditions** round-trip for **Router** branches (the generator emits them as
  `add_conditional_edges(..., route_*, {cond: target})`, losslessly) but **not** for ReAct
  agent↔tool wiring: that goes through LangGraph's `tools_condition` prebuilt, whose fixed
  `"tools"`/`END` keys discard the spec's condition labels. Dropping them is behaviourally
  lossless — re-applying the plain agent→tool / agent→done edges regenerates identical wiring.
"""

from __future__ import annotations

import pytest
from _equivalence import CORPUS
from _equivalence import channels as _channels
from _equivalence import topology as _topology
from calypr_codegen import generate_python
from calypr_compiler.golden import input_agent_output
from calypr_dsl import GraphSpec
from calypr_nodes import graph_channels
from calypr_roundtrip import parse_python


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_topology_round_trips(graph: GraphSpec) -> None:
    result = parse_python(generate_python(graph))
    parsed = result.spec

    assert {n.id for n in parsed.nodes} == {n.id for n in graph.nodes}
    assert parsed.entry == graph.entry
    assert _topology(parsed) == _topology(graph)

    # Router branch conditions survive; ReAct tools_condition labels do not (see module
    # docstring). Router source ids are taken from the original graph so this holds regardless
    # of how the parsed nodes were typed.
    routers = {n.id for n in graph.nodes if n.type == "router"}
    cond = lambda edges: {  # noqa: E731
        (e.source, e.target): e.condition for e in edges if e.source in routers
    }
    assert cond(parsed.edges) == cond(graph.edges)


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_state_channels_round_trip(graph: GraphSpec) -> None:
    # The generated State unions node-owned channels with the spec's state, so compare against
    # graph_channels(...) — the same augmentation the generator applies.
    result = parse_python(generate_python(graph))
    expected = graph_channels(graph.nodes, graph.state)
    assert _channels(result.spec.state) == _channels(expected)


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_trailer_restores_identity(graph: GraphSpec) -> None:
    parsed = parse_python(generate_python(graph)).spec
    assert (parsed.id, parsed.name, parsed.description) == (
        graph.id,
        graph.name,
        graph.description,
    )


def test_trailer_restores_layout() -> None:
    graph = input_agent_output()
    graph.nodes[0].position = {"x": 10.0, "y": 20.0}
    parsed = parse_python(generate_python(graph)).spec
    positions = {n.id: n.position for n in parsed.nodes}
    assert positions["in"] == {"x": 10.0, "y": 20.0}


def test_trailer_deletion_still_parses() -> None:
    graph = input_agent_output()
    code = generate_python(graph)
    stripped = "\n".join(
        line for line in code.splitlines() if not line.strip().startswith("# calypr:")
    )
    result = parse_python(stripped)

    # Topology + state still recovered; layout gone; id falls back; name from the docstring.
    assert {n.id for n in result.spec.nodes} == {n.id for n in graph.nodes}
    assert all(n.position is None for n in result.spec.nodes)
    assert result.spec.id == "parsed"
    assert result.spec.name == graph.name


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_node_types_recovered(graph: GraphSpec) -> None:
    # Week-6 recognisers recover every node's type + config for the shipped corpus — nothing
    # degrades to a `code` node, and no node is mistaken for another type.
    result = parse_python(generate_python(graph))
    assert result.degraded_nodes == []
    got = {n.id: n.type for n in result.spec.nodes}
    assert got == {n.id: n.type for n in graph.nodes}


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_codegen_fixed_point(graph: GraphSpec) -> None:
    # The registry-wide equivalence the plan pins Week 6 to: parsing generated code and
    # regenerating from the recovered spec is a fixed point (`generate ∘ parse ∘ generate`
    # is byte-identical to `generate`). This proves the recovered config reproduces the code,
    # which is the "no ceiling" guarantee — canvas → code → canvas → code is stable.
    code = generate_python(graph)
    assert generate_python(parse_python(code).spec) == code


def test_every_registered_node_type_has_a_recogniser() -> None:
    # Guards against a new node type shipping without a `parse()` inverse: every registered
    # type (except the `code` fallback itself) must appear — recognised — somewhere in the
    # corpus round-trip above. If this fails, add the node to a template and give it a parse().
    from calypr_nodes import all_node_types

    recovered: set[str] = set()
    for graph in CORPUS:
        recovered.update(n.type for n in parse_python(generate_python(graph)).spec.nodes)
    missing = set(all_node_types()) - recovered - {"code"}
    assert not missing, f"node types with no round-trip coverage: {sorted(missing)}"


def test_unrecognised_node_degrades_to_code() -> None:
    # The graceful-degradation contract: a node function no recogniser matches becomes a `code`
    # node with its source preserved verbatim — the parser never rejects the surface.
    code = (
        "def node_mystery(state: State) -> dict:\n"
        '    """Something no recogniser matches."""\n'
        '    return {"out": weird_custom_logic(state)}\n'
        "\n\n"
        "def build_graph():\n"
        "    graph = StateGraph(State)\n"
        '    graph.add_node("mystery", node_mystery)\n'
        '    graph.add_edge(START, "mystery")\n'
        "    return graph.compile()\n"
    )
    result = parse_python(code)
    assert result.degraded_nodes == ["mystery"]
    node = result.spec.nodes[0]
    assert node.type == "code"
    assert "weird_custom_logic" in node.config["code"]


def test_missing_build_graph_is_graceful() -> None:
    result = parse_python("x = 1\n")
    assert result.spec.nodes == []
    assert any("build_graph" in w for w in result.warnings)


def test_syntax_error_is_graceful() -> None:
    result = parse_python("def build_graph(:\n")  # deliberately broken
    assert result.spec.nodes == []
    assert any("syntax error" in w for w in result.warnings)
