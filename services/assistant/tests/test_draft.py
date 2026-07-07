"""The draft pipeline: parsing, forbidden-node rejection, and the repair loop."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import pytest
from calypr_assistant import draft_graph
from calypr_assistant.draft import ParseError, _parse_and_normalize
from calypr_assistant.events import Error, Graph, Status, Usage
from calypr_compiler import validate_graph
from calypr_compiler.golden import input_agent_output
from calypr_model import Done, StreamEvent, TextDelta
from calypr_model import Usage as ModelUsage


class ScriptedModel:
    """A ModelClient that returns a queued reply per `stream()` call (invalid-then-valid)."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def stream(self, **_kwargs) -> AsyncIterator[StreamEvent]:
        text = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        for i in range(0, len(text), 8):
            yield TextDelta(text=text[i : i + 8])
        yield ModelUsage(input_tokens=10, output_tokens=20)
        yield Done(text=text)


def _valid_json() -> str:
    return json.dumps(input_agent_output().model_dump(mode="json"))


def _invalid_no_output() -> str:
    spec = input_agent_output().model_dump(mode="json")
    spec["nodes"] = [n for n in spec["nodes"] if n["type"] != "output"]
    spec["edges"] = [e for e in spec["edges"] if e["target"] != "out"]
    return json.dumps(spec)


async def _collect(gen) -> list:
    return [ev async for ev in gen]


def test_parse_handles_fenced_and_noisy_json() -> None:
    fenced = "```json\n" + _valid_json() + "\n```"
    spec = _parse_and_normalize("Sure! Here you go:\n" + fenced + "\nHope that helps.")
    assert not [i for i in validate_graph(spec) if i.severity == "error"]


def test_parse_rejects_code_nodes() -> None:
    spec = input_agent_output().model_dump(mode="json")
    spec["nodes"].append({"id": "c", "type": "code", "config": {}})
    with pytest.raises(ParseError, match="forbidden"):
        _parse_and_normalize(json.dumps(spec))


def test_parse_assigns_fresh_id_and_strips_positions() -> None:
    raw = input_agent_output().model_dump(mode="json")
    raw["id"] = "attacker-supplied"
    raw["nodes"][0]["position"] = {"x": 5, "y": 5}
    spec = _parse_and_normalize(json.dumps(raw))
    assert spec.id != "attacker-supplied"
    assert all(n.position is None for n in spec.nodes)


async def test_repair_loop_succeeds_on_second_attempt() -> None:
    model = ScriptedModel([_invalid_no_output(), _valid_json()])
    events = await _collect(
        draft_graph([{"role": "user", "content": "hi"}], None, "fake", client=model)
    )
    assert model.calls == 2  # first invalid, second valid
    assert any(isinstance(e, Status) and e.phase == "repairing" for e in events)
    graphs = [e for e in events if isinstance(e, Graph)]
    assert len(graphs) == 1
    assert not [i for i in validate_graph(graphs[0].spec) if i.severity == "error"]
    assert not any(isinstance(e, Error) for e in events)


async def test_repair_loop_gives_up_after_max_retries() -> None:
    model = ScriptedModel([_invalid_no_output()])  # always invalid
    events = await _collect(
        draft_graph([{"role": "user", "content": "hi"}], None, "fake", client=model)
    )
    assert model.calls == 3  # initial + 2 repairs
    errors = [e for e in events if isinstance(e, Error)]
    assert len(errors) == 1
    assert errors[0].issues  # carries the validation issues
    assert not any(isinstance(e, Graph) for e in events)


async def test_usage_is_emitted() -> None:
    model = ScriptedModel([_valid_json()])
    events = await _collect(
        draft_graph([{"role": "user", "content": "hi"}], None, "fake", client=model)
    )
    assert any(isinstance(e, Usage) and e.model == "fake" for e in events)
