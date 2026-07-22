"""Every config field is either editable on the canvas or explicitly justified here.

Phase 2c. The engine's config models are the source of truth for what a block *can* do; the
canvas panel is what a user can actually reach. Nothing kept those two in step, and the gap was
real: `agent_type` had a fully-written options list in `graph.ts` that no control ever rendered,
so a hand-built Agent was stuck on `model_based` — and the panel showed reflection/utility/goal
fields that could therefore never appear.

This reads the panel's source and asserts every field is accounted for. Adding a field to a
config model now fails the suite until you either build a control or write down why not, which
is the only way an audit like this stays true a month later.

It parses TSX with regexes, which is crude but honest about its own limits: it can only see
`set({ key: … })` calls, so a control wired some other way must be added to KNOWN_EXPOSED with
a note. The alternative — asserting nothing — is what let the gap open in the first place.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from calypr_nodes.registry import _REGISTRY

PANEL = (
    Path(__file__).resolve().parents[3]
    / "apps/web/src/components/canvas/ConfigPanel.tsx"
)

# --- fields deliberately absent from the panel, with the reason ---------------------------------
#
# Grouped by *why*, because the reasons are not equivalent: wiring is a design decision, inert is
# a defect we haven't paid off yet, and server-resolved is a security boundary.

#: Channel names — which state key a block reads and writes. Expressed by drawing edges on the
#: canvas, not by typing channel names, and exposing them would let a user break their own graph
#: in a way the edges then contradict.
WIRING = {
    "input_channel",
    "output_channel",
    "source_channel",
    "target_channel",
    "memory_channel",
    "images_channel",
    "prompt_channel",
    "score_channel",
    "rationale_channel",
    "route_channel",
}

#: Declared on the config model but read by *nothing* — see `test_no_new_inert_config_fields`.
#: A control here would be a knob that does nothing, which is worse than its absence. These need
#: to be implemented or deleted; tracked in TODO.md.
INERT = {
    ("agent", "max_steps"),
    ("agent", "utility_criteria"),
    ("input", "mode"),
    ("output", "stream"),
    ("tool", "http_method"),  # also Literal["GET"] — there is nothing to choose yet
}

#: Resolved server-side and never user-editable: the vault injects these just before compile, and
#: letting the client set them would hand it a way to forge credentials/headers.
SERVER_RESOLVED = {
    ("tool", "mcp_headers"),
}

#: Set through a control that doesn't call `set({...})` literally, so the parser can't see it.
KNOWN_EXPOSED = {
    ("tool", "mcp_connector_ref"),  # the Connector dropdown, set via a handler
    ("retriever", "embedding_model"),  # rendered by the pgvector branch
}


def _panel_source() -> str:
    assert PANEL.exists(), f"config panel not found at {PANEL}"
    return PANEL.read_text()


def _component_bodies(src: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    starts = [(m.group(1), m.start()) for m in re.finditer(r"^function (\w+)\(", src, re.M)]
    for i, (name, pos) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(src)
        bodies[name] = src[pos:end]
    return bodies


def _keys_written(fn: str, bodies: dict[str, str], seen: set[str] | None = None) -> set[str]:
    """Config keys a component writes, following the child components it renders."""
    seen = seen if seen is not None else set()
    if fn in seen or fn not in bodies:
        return set()
    seen.add(fn)
    body = bodies[fn]
    keys = set(re.findall(r"set\(\{\s*\n?\s*(\w+):", body))
    for child in re.findall(r"<(\w+Fields?)\b", body):
        keys |= _keys_written(child, bodies, seen)
    return keys


def _exposed_by_type() -> dict[str, set[str]]:
    src = _panel_source()
    bodies = _component_bodies(src)
    dispatch = dict(re.findall(r'type === "(\w+)" \? <(\w+)', src))
    # The `code`/`input`/`output` branches are inline in ConfigPanel itself.
    tail = src[src.index("export function ConfigPanel") :]
    tail_keys = set(re.findall(r"set\(\{\s*\n?\s*(\w+):", tail))

    out: dict[str, set[str]] = {}
    for node_type in _REGISTRY:
        component = dispatch.get(node_type)
        keys = _keys_written(component, bodies) if component else set()
        if node_type in ("code", "input", "output"):
            keys |= tail_keys
        out[node_type] = keys
    return out


EXPOSED = _exposed_by_type()


@pytest.mark.parametrize("node_type", sorted(_REGISTRY))
def test_every_config_field_is_editable_or_justified(node_type: str):
    fields = set(_REGISTRY[node_type].config_model.model_fields)
    excused = (
        WIRING
        | {f for t, f in INERT if t == node_type}
        | {f for t, f in SERVER_RESOLVED if t == node_type}
        | {f for t, f in KNOWN_EXPOSED if t == node_type}
    )
    unreachable = fields - EXPOSED[node_type] - excused
    assert unreachable == set(), (
        f"{node_type}: {sorted(unreachable)} can be set in the engine but not on the canvas. "
        "Add a control, or add it to WIRING / INERT / SERVER_RESOLVED with the reason."
    )


def test_the_agent_ladder_is_selectable():
    """The specific gap this file was written for. `AGENT_TYPE_OPTIONS` existed in graph.ts with
    six written labels and nothing rendered it, so every hand-built agent was `model_based` and
    the goal/reflection/utility fields below were dead UI."""
    src = _panel_source()
    assert "AGENT_TYPE_OPTIONS" in src, "the agent type ladder has no control again"
    assert 'id="cfg-agent-type"' in src


def test_excuses_refer_to_real_fields():
    """An excuse for a field that no longer exists is stale — it would silently keep excusing a
    field someone later re-adds under the same name."""
    for group, name in (
        (INERT, "INERT"),
        (SERVER_RESOLVED, "SERVER_RESOLVED"),
        (KNOWN_EXPOSED, "KNOWN_EXPOSED"),
    ):
        for node_type, field in group:
            assert node_type in _REGISTRY, f"{name}: unknown node type {node_type!r}"
            assert field in _REGISTRY[node_type].config_model.model_fields, (
                f"{name}: {node_type}.{field} is no longer a config field — drop the excuse"
            )


def test_wiring_excuses_are_all_channels():
    """Guards the escape hatch: WIRING is meant for state-channel names only, so it can't quietly
    become a dumping ground for any field somebody didn't want to build a control for."""
    assert all(f.endswith("_channel") for f in WIRING)
