"""`AgentSummary.preview` — the graph shape a dashboard card draws.

Pure projection over the stored JSON, so these need no database: they call `_preview_of`
directly. The thing worth protecting is that it never raises and never carries config — it runs
once per project on every dashboard load, and a thumbnail must not be what 500s the list.
"""

from __future__ import annotations

from calypr_api.routers.agents import _PREVIEW_MAX_NODES, _preview_of


def _spec(nodes, edges=None):
    return {"nodes": nodes, "edges": edges or []}


def test_projects_types_positions_and_edges():
    p = _preview_of(
        _spec(
            [
                {"id": "a", "type": "input", "position": {"x": 0, "y": 10}},
                {"id": "b", "type": "agent", "position": {"x": 240, "y": 10}},
            ],
            [{"source": "a", "target": "b"}],
        )
    )
    assert p is not None
    assert [n.type for n in p.nodes] == ["input", "agent"]
    assert (p.nodes[1].x, p.nodes[1].y) == (240.0, 10.0)
    # Edges are indices into `nodes`, not ids: the ids only mean something next to the config
    # this preview deliberately drops.
    assert p.edges == [(0, 1)]


def test_carries_no_config():
    """The whole point of a separate shape: prompts and keys never reach the dashboard."""
    p = _preview_of(
        _spec(
            [
                {
                    "id": "a",
                    "type": "agent",
                    "position": {"x": 0, "y": 0},
                    "config": {"prompt": "SECRET SYSTEM PROMPT", "api_key": "sk-nope"},
                }
            ]
        )
    )
    assert p is not None
    assert p.model_dump_json().find("SECRET") == -1
    assert "sk-nope" not in p.model_dump_json()


def test_edges_to_dropped_nodes_are_discarded():
    """An edge naming a node the preview didn't keep would index out of bounds in the client."""
    nodes = [{"id": f"n{i}", "type": "agent", "position": {"x": i, "y": 0}} for i in range(60)]
    edges = [{"source": "n0", "target": "n59"}]  # n59 is past the cap
    p = _preview_of(_spec(nodes, edges))
    assert p is not None
    assert len(p.nodes) == _PREVIEW_MAX_NODES
    assert p.edges == []


def test_missing_positions_lay_out_as_a_column():
    """Graphs saved before positions were persisted still show how many blocks they have."""
    p = _preview_of(_spec([{"id": "a", "type": "input"}, {"id": "b", "type": "output"}]))
    assert p is not None
    assert [n.x for n in p.nodes] == [0.0, 0.0]
    assert p.nodes[0].y != p.nodes[1].y


def test_degrades_rather_than_raising():
    """Every one of these used to be a 500 on the whole project list."""
    assert _preview_of(None) is None
    assert _preview_of("not a graph") is None
    assert _preview_of({}) is None
    assert _preview_of(_spec([])) is None
    # Junk entries are skipped, not fatal.
    assert _preview_of(_spec(["nonsense", {"id": "a"}, {"type": "agent"}])) is None
    p = _preview_of(_spec([{"id": "a", "type": "input"}, 42], [{"source": "a"}, "junk"]))
    assert p is not None and len(p.nodes) == 1 and p.edges == []
