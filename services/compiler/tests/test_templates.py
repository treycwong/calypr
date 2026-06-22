"""Every archetype template is a real, runnable agent: it validates, runs with the fake
model, and round-trips to ruff-clean Python — the wedge's correctness floor across the
whole agent ladder."""

from __future__ import annotations

import subprocess

import pytest
from calypr_codegen import generate_python
from calypr_compiler import TEMPLATES, validate_graph
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext
from calypr_runtime import run


def test_archetypes_present():
    ids = [t.id for t in TEMPLATES]
    assert ids == [
        "tpl-simple-reflex",
        "tpl-model-based",
        "tpl-goal-based",
        "tpl-utility-based",
        "tpl-reflection",
        "tpl-learning",
        "tpl-react",
    ]


@pytest.mark.parametrize("graph", TEMPLATES, ids=lambda g: g.id)
def test_template_validates(graph):
    errors = [i for i in validate_graph(graph) if i.severity == "error"]
    assert errors == [], errors


@pytest.mark.parametrize("graph", TEMPLATES, ids=lambda g: g.id)
async def test_template_runs_with_fake_model(graph):
    result = await run(graph, NodeContext(model=FakeModelClient()), "hello there")
    assert isinstance(result.get("output"), str)
    assert result["output"]


@pytest.mark.parametrize("graph", TEMPLATES, ids=lambda g: g.id)
def test_template_codegen_is_ruff_clean(graph):
    code = generate_python(graph)
    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, f"{graph.id} codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout
