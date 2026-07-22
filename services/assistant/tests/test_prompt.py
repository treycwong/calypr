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


def test_prompt_teaches_the_react_tool_wiring():
    """Every few-shot used to be tool-free, so the model had never seen a Tool node wired and
    reached for a Router branch instead — which binds the tools to a node that discards them."""
    from calypr_assistant.prompt import system_prompt

    prompt = system_prompt()
    assert '"type":"tool"' in prompt, "no few-shot contains a Tool node"
    # The ReAct loop as the notion_assistant template wires it: agent -> tool on 'tools'.
    assert '"source":"agent","target":"tools","condition":"tools"' in prompt
    assert "never from a" in prompt and "router:" in prompt
