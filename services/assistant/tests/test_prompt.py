"""The system prompt is registry-derived — every node type appears, none is dropped."""

from __future__ import annotations

from calypr_assistant import system_prompt
from calypr_assistant.prompt import _few_shots, _node_catalog
from calypr_nodes import all_node_types


def test_catalog_includes_every_registry_type() -> None:
    catalog = _node_catalog()
    for type_id in all_node_types():
        assert f"- {type_id}:" in catalog, f"{type_id} missing from node catalog"


def test_code_node_listed_but_marked_forbidden() -> None:
    catalog = _node_catalog()
    assert "- code:" in catalog  # not silently dropped
    assert "FORBIDDEN" in catalog


def test_system_prompt_embeds_schema_catalog_and_examples() -> None:
    prompt = system_prompt()
    assert "GraphSpec JSON schema" in prompt
    assert "Node catalog" in prompt
    assert "HARD RULES" in prompt
    # a few-shot spec is embedded verbatim
    assert '"type":"retriever"' in _few_shots()
