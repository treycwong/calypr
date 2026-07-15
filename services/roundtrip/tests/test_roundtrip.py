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
- **edge ids** and **node config** are not compared (every node still degrades to a `code` node
  until the Week-6 recognisers land);
- **edge conditions** round-trip for **Router** branches (the generator emits them as
  `add_conditional_edges(..., route_*, {cond: target})`, losslessly) but **not** for ReAct
  agent↔tool wiring: that goes through LangGraph's `tools_condition` prebuilt, whose fixed
  `"tools"`/`END` keys discard the spec's condition labels. Dropping them is behaviourally
  lossless — re-applying the plain agent→tool / agent→done edges regenerates identical wiring.
"""

from __future__ import annotations

import pytest
from calypr_codegen import generate_python
from calypr_codegen.generate import _PYTYPE
from calypr_compiler import STARTERS
from calypr_compiler.golden import input_agent_output
from calypr_dsl import GraphSpec, StateChannel
from calypr_nodes import graph_channels
from calypr_roundtrip import parse_python

CORPUS: list[GraphSpec] = [input_agent_output(), *STARTERS]


def _topology(graph: GraphSpec) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in graph.edges}


def _channels(chs: list[StateChannel]) -> set[tuple[str, str, str]]:
    # Normalise each channel by the Python type the generator would emit, so the forward map's
    # many-to-one lossiness (string/str → str) doesn't cause spurious inequality.
    return {(c.key, str(c.reducer), _PYTYPE.get(c.type, "Any")) for c in chs}


@pytest.mark.parametrize("graph", CORPUS, ids=lambda g: g.id)
def test_topology_round_trips(graph: GraphSpec) -> None:
    result = parse_python(generate_python(graph))
    parsed = result.spec

    assert {n.id for n in parsed.nodes} == {n.id for n in graph.nodes}
    assert parsed.entry == graph.entry
    assert _topology(parsed) == _topology(graph)

    # Router branch conditions survive; ReAct tools_condition labels do not (see module
    # docstring). Router source ids come from the original graph — PR-1 degrades every parsed
    # node to `code`, so parsed node types can't be filtered on.
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
def test_all_nodes_degrade_to_code_in_pr1(graph: GraphSpec) -> None:
    # PR-1 has no node recognisers yet, so every node is reported degraded, with its source kept.
    result = parse_python(generate_python(graph))
    assert set(result.degraded_nodes) == {n.id for n in graph.nodes}
    assert all(n.type == "code" for n in result.spec.nodes)


def test_missing_build_graph_is_graceful() -> None:
    result = parse_python("x = 1\n")
    assert result.spec.nodes == []
    assert any("build_graph" in w for w in result.warnings)


def test_syntax_error_is_graceful() -> None:
    result = parse_python("def build_graph(:\n")  # deliberately broken
    assert result.spec.nodes == []
    assert any("syntax error" in w for w in result.warnings)
