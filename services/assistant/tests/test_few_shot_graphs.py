"""Every few-shot the assistant learns from is a graph that actually works.

The model's picture of "a correct Calypr graph" is exactly the examples in the prompt — so an
invalid few-shot doesn't merely fail a test, it *teaches the mistake* to every generation. That
is not hypothetical: before PR #41 no few-shot contained a Tool node at all, so asked to read a
Notion workspace the model reached for the one control-flow shape it had seen (a Router with a
"notion" branch) and produced a graph whose agent silently had no tools.

So the few-shots are held to the same bar as a shipped starter — validate, run, and stay inside
the rules the prompt itself lays down. Most come from `templates.py` (covered by
`test_templates.py`), but `_anime_image` and `_spoken_assistant` are built inside `prompt.py`
and nothing else exercises them.
"""

from __future__ import annotations

import pytest
from calypr_assistant.prompt import few_shot_pairs, system_prompt
from calypr_compiler import validate_graph
from calypr_model import FakeImageClient, FakeModelClient, FakeTTSClient
from calypr_nodes import NodeContext
from calypr_runtime import run

PAIRS = few_shot_pairs()
IDS = [spec.id for _, spec in PAIRS]


def test_there_are_few_shots_to_check():
    # Guards against the extraction silently returning [] and every test below vacuously passing.
    assert len(PAIRS) >= 5


@pytest.mark.parametrize(("request_text", "spec"), PAIRS, ids=IDS)
def test_few_shot_validates(request_text: str, spec):
    errors = [i for i in validate_graph(spec) if i.severity == "error"]
    assert errors == [], f"{spec.id} teaches a graph the compiler would refuse: {errors}"


@pytest.mark.parametrize(("request_text", "spec"), PAIRS, ids=IDS)
async def test_few_shot_runs(request_text: str, spec):
    """Validation is structural; this is the "and it actually answers" half. Fake clients on all
    three model seams keep it keyless — the image/TTS few-shots name real billed models."""
    ctx = NodeContext(
        model=FakeModelClient(), image_model=FakeImageClient(), tts_model=FakeTTSClient()
    )
    result = await run(spec, ctx, "hello there")
    assert isinstance(result.get("output"), str) and result["output"]


@pytest.mark.parametrize(("request_text", "spec"), PAIRS, ids=IDS)
def test_few_shot_obeys_the_rules_the_prompt_states(request_text: str, spec):
    """The prompt forbids the Custom Code node and requires an Input entry — an example that
    breaks a stated rule teaches the model that the rules are optional."""
    assert not any(n.type == "code" for n in spec.nodes), (
        "the prompt lists `code` as forbidden; a few-shot using it contradicts that"
    )
    entry = next((n for n in spec.nodes if n.id == spec.entry), None)
    assert entry is not None and entry.type == "input"


@pytest.mark.parametrize(("request_text", "spec"), PAIRS, ids=IDS)
def test_no_few_shot_hangs_a_tool_node_off_a_router(request_text: str, spec):
    """The PR #41 shape, pinned by name. `validate_graph` rejects it as `tool_node_unbound`, so
    this is redundant *while that rule holds* — it's here because this specific mistake reached
    users once, and a prompt example is how it would come back."""
    binders = {n.id for n in spec.nodes if n.type in ("agent", "responder", "revisor")}
    for node in (n for n in spec.nodes if n.type == "tool"):
        sources = {e.source for e in spec.edges if e.target == node.id}
        assert sources & binders, (
            f"{spec.id}: Tool node {node.id!r} is fed only by {sorted(sources)} — nothing binds "
            "its tools, so the model would get none"
        )


def test_every_few_shot_request_reaches_the_prompt():
    """The pairs are useless if the rendering drops them; assert each request line is present."""
    prompt = system_prompt()
    for request_text, _ in PAIRS:
        assert request_text in prompt
