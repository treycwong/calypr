from calypr_dsl import (
    SCHEMA_VERSION,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    Reducer,
    StateChannel,
)


def test_minimal_graphspec_roundtrips():
    g = GraphSpec(
        id="g1",
        name="Echo",
        state=[StateChannel(key="messages", type="list", reducer=Reducer.append)],
        nodes=[NodeSpec(id="in", type="input"), NodeSpec(id="out", type="output")],
        edges=[EdgeSpec(id="e1", source="in", target="out")],
        entry="in",
    )
    loaded = GraphSpec.model_validate_json(g.model_dump_json())
    assert loaded == g
    assert loaded.schema_version == SCHEMA_VERSION


def test_json_schema_has_expected_defs():
    schema = GraphSpec.model_json_schema()
    assert schema["title"] == "GraphSpec"
    for name in ("StateChannel", "NodeSpec", "EdgeSpec", "Reducer"):
        assert name in schema["$defs"], f"missing $def: {name}"
