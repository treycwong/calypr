"""Every starter — framework or use-case template — is a real, runnable agent: it validates,
runs with the fake model, and round-trips to ruff-clean Python (the wedge's correctness floor)."""

from __future__ import annotations

import subprocess

import pytest
from calypr_codegen import generate_python
from calypr_compiler import FRAMEWORKS, STARTERS, TEMPLATES, validate_graph
from calypr_model import FakeImageClient, FakeModelClient, FakeTTSClient
from calypr_nodes import NodeContext
from calypr_runtime import run


def test_frameworks_present():
    ids = [t.id for t in FRAMEWORKS]
    assert ids == [
        "tpl-simple-reflex",
        "tpl-model-based",
        "tpl-goal-based",
        "tpl-utility-based",
        "tpl-reflection",
        "tpl-learning",
        "tpl-react",
        "tpl-mcp-react",
        "tpl-reflexion",
        "tpl-rag",
    ]


def test_use_case_templates_present():
    ids = [t.id for t in TEMPLATES]
    assert ids == [
        "tpl-market-research",
        "tpl-customer-support",
        "tpl-contract-review",
        "tpl-routing",
        "tpl-trip-planner",
        "tpl-image-generation",
        "tpl-text-to-speech",
        "tpl-translate-speak",
        "tpl-label-reader",
        "tpl-alt-text",
        "tpl-notion-assistant",
        "tpl-image-finder",
    ]


def test_orchestrator_worker_fans_out():
    """The Trip itinerary planner is a static orchestrator–worker: the orchestrator fans out to
    several parallel workers that fan in to one synthesizer (every worker feeds it)."""
    g = next(t for t in TEMPLATES if t.id == "tpl-trip-planner")
    fan_out = [e for e in g.edges if e.source == "orchestrator"]
    fan_in = [e for e in g.edges if e.target == "synthesizer"]
    assert len(fan_out) >= 2  # parallel fan-out
    assert len(fan_in) == len(fan_out)  # every worker feeds the synthesizer (fan-in)


@pytest.mark.parametrize("graph", STARTERS, ids=lambda g: g.id)
def test_starter_validates(graph):
    errors = [i for i in validate_graph(graph) if i.severity == "error"]
    assert errors == [], errors


@pytest.mark.parametrize("graph", STARTERS, ids=lambda g: g.id)
async def test_starter_runs_with_fake_model(graph):
    # Image/TTS templates default to real (billed) models in production; inject Fake clients here
    # so the whole starter matrix stays keyless/offline in CI regardless of each node's `model`.
    ctx = NodeContext(
        model=FakeModelClient(), image_model=FakeImageClient(), tts_model=FakeTTSClient()
    )
    result = await run(graph, ctx, "hello there")
    assert isinstance(result.get("output"), str)
    assert result["output"]


@pytest.mark.parametrize("graph", STARTERS, ids=lambda g: g.id)
def test_starter_codegen_is_ruff_clean(graph):
    code = generate_python(graph)
    fmt = subprocess.run(["ruff", "format", "-"], input=code, capture_output=True, text=True)
    assert fmt.stdout == code, f"{graph.id} codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout


def test_image_finder_prompts_for_an_inline_preview():
    """The found photo only previews in the playground when the agent emits markdown *image*
    syntax — the leading `!`. A plain `[label](url)` link renders as text, which is what the
    first cut of this template produced. The prompt is what makes the difference, so pin it."""
    graph = next(g for g in TEMPLATES if g.id == "tpl-image-finder")
    prompt = next(n for n in graph.nodes if n.type == "agent").config["system_prompt"]
    assert "![" in prompt
    assert "leading ! is required" in prompt


@pytest.mark.parametrize("graph", STARTERS, ids=lambda g: g.id)
def test_no_starter_ships_the_fake_model(graph):
    """A starter must not be configured with the keyless `fake` model.

    `fake` is a *test* seam: it answers "Echo: <your message>". Shipping it in a template means
    a production user picks that starter and gets canned nonsense — Reflexion did exactly that,
    with both of its LLM nodes fake, so the whole reply was an echo. Routing was subtler and
    worse: the classifier was fake, so the branch decision was canned while the surrounding
    agents answered normally, and it *looked* fine.

    Nothing else catches this. Every test above injects Fake clients through `NodeContext`
    regardless of what a node configures, so a template reads identically in CI whether it says
    `fake` or `gpt-4o-mini` — which is precisely why this went to production unnoticed and had
    to be found by running the live site."""
    fakes = [
        n.id for n in graph.nodes if isinstance(n.config, dict) and n.config.get("model") == "fake"
    ]
    assert fakes == [], f"{graph.id} ships the fake model on {fakes}"
