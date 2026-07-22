"""The wiring matrix: every node type wired every which way, and every rejection by name.

`test_templates.py` proves the *curated* graphs work. This file proves the ones nobody curated
— the shapes a user draws on the canvas or the assistant invents — either run or are refused
with an actionable reason. It exists because of PR #41, where one bug report produced four
"the nodes don't connect" defects, every one of which validated clean and then quietly did
nothing: a Tool node fed from a Router bound no tools, and the agent said "I can't access
Notion" with nothing anywhere to say why.

Two invariants, and the first is the one that matters:

1. **Accepted ⇒ runnable.** If `validate_graph` reports no errors, the graph runs to completion
   and produces output. Silent acceptance of a graph that then does nothing is the failure mode
   this whole file is aimed at.
2. **Rejected ⇒ actionable.** Every error carries a code from the validator's own vocabulary
   and points at the node or edge to fix, so the canvas can highlight it and the assistant can
   repair against it.

Plus a meta-test: every `code=` the validator can emit has a case here that provokes it. A new
rule without a test fails the suite rather than passing unnoticed.
"""

from __future__ import annotations

import inspect
import itertools
import re

import pytest
from calypr_compiler import STARTERS, validate_graph
from calypr_compiler import validate as validate_module
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import FakeImageClient, FakeModelClient, FakeTTSClient
from calypr_nodes import NodeContext
from calypr_nodes.registry import all_node_types, graph_channels
from calypr_runtime import run

# --- fixtures ---------------------------------------------------------------------------------

BASE_STATE = [
    StateChannel(key="input", type="string", reducer=Reducer.last),
    StateChannel(key="messages", type="messages", reducer=Reducer.append),
    StateChannel(key="output", type="string", reducer=Reducer.last),
]


def _representatives() -> dict[str, dict]:
    """One known-good config per node type, harvested from the shipped starters.

    Harvested rather than hand-written so the matrix can't drift from what the product actually
    generates — if a node gains a required field, the starters gain it too and this follows.
    `code` is the exception: it's the escape hatch, so no starter uses it."""
    reps: dict[str, dict] = {}
    for graph in STARTERS:
        for node in graph.nodes:
            reps.setdefault(node.type, dict(node.config))
    reps.setdefault("code", {"code": "state['output'] = 'ok'"})
    return reps


REPRESENTATIVE = _representatives()

# Input and Output bracket every graph below rather than appearing in the middle of one.
MIDDLE_TYPES = sorted(set(all_node_types()) - {"input", "output"})


def _fake_ctx() -> NodeContext:
    """Fake clients for all three model seams, so image/TTS nodes — which default to real,
    billed models in production — stay keyless and free here, as in `test_templates.py`."""
    return NodeContext(
        model=FakeModelClient(), image_model=FakeImageClient(), tts_model=FakeTTSClient()
    )


def _linear(*middle: tuple[str, str]) -> GraphSpec:
    """Input → …middle… → Output, with each middle node's representative config."""
    nodes = [NodeSpec(id="in", type="input", config=REPRESENTATIVE["input"])]
    nodes += [NodeSpec(id=nid, type=ntype, config=REPRESENTATIVE[ntype]) for nid, ntype in middle]
    nodes.append(NodeSpec(id="out", type="output", config=REPRESENTATIVE["output"]))
    ids = [n.id for n in nodes]
    spec = GraphSpec(
        id="matrix",
        name="matrix",
        state=list(BASE_STATE),
        nodes=nodes,
        edges=[
            EdgeSpec(id=f"e{i}", source=a, target=b)
            for i, (a, b) in enumerate(itertools.pairwise(ids))
        ],
        entry="in",
    )
    # Mirror the runtime: a node may own channels the caller never declared.
    spec.state = graph_channels(spec.nodes, spec.state)
    return spec


def _errors(spec: GraphSpec) -> list:
    return [i for i in validate_graph(spec) if i.severity == "error"]


# --- coverage ---------------------------------------------------------------------------------


def test_every_registered_node_type_is_represented():
    """A node type nobody can build a graph with is a node type nobody tests. Registering one
    without adding it to a starter (or exempting it here) fails this."""
    missing = set(all_node_types()) - set(REPRESENTATIVE)
    assert missing == set(), f"no representative config for {sorted(missing)}"


def test_code_is_the_only_node_type_absent_from_the_starters():
    """The Custom Code node is the escape hatch — its body is whatever the user pastes, so no
    starter ships one. Every *other* type must appear in a shipped graph, or users meet it for
    the first time with no working example to copy."""
    in_starters = {n.type for g in STARTERS for n in g.nodes}
    assert set(all_node_types()) - in_starters == {"code"}


# --- invariant 1: accepted ⇒ runnable ----------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    list(itertools.product(MIDDLE_TYPES, repeat=2)),
    ids=lambda t: t,
)
async def test_accepted_pairs_run_and_rejected_pairs_say_why(first: str, second: str):
    """Input → A → B → Output for every ordered pair of node types.

    Either the validator refuses the pair with a named, located error, or the graph runs to
    completion and yields output. What must never happen is the third case: accepted, run, and
    silently useless."""
    spec = _linear(("a", first), ("b", second))
    errors = _errors(spec)

    if errors:
        for issue in errors:
            assert issue.code, f"{first}→{second}: an error with no code"
            assert issue.node_id or issue.edge_id, (
                f"{first}→{second}: [{issue.code}] doesn't say what to fix — the canvas can't "
                "highlight it and the assistant can't repair against it"
            )
        return

    result = await run(spec, _fake_ctx(), "hello there")
    assert isinstance(result.get("output"), str) and result["output"], (
        f"{first}→{second} validated clean but produced no output — the exact silent failure "
        "this matrix exists to catch"
    )


# --- invariant 2: every rule fires, and every rule is tested ------------------------------------


def _bad_entry() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.entry = "nope"
    return spec


def _no_entry() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.entry = ""
    return spec


def _duplicate_ids() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.nodes.append(NodeSpec(id="a", type="agent", config=REPRESENTATIVE["agent"]))
    return spec


def _unknown_type() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.nodes[1] = NodeSpec(id="a", type="teleporter", config={})
    return spec


def _invalid_config() -> GraphSpec:
    spec = _linear(("a", "router"))
    spec.nodes[1] = NodeSpec(id="a", type="router", config={"kind": "not-a-kind"})
    return spec


def _dangling_edge() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.edges.append(EdgeSpec(id="dangle", source="a", target="ghost"))
    return spec


def _no_output() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.nodes = [n for n in spec.nodes if n.type != "output"]
    spec.edges = [e for e in spec.edges if e.target != "out"]
    return spec


def _dead_end() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.edges = [e for e in spec.edges if e.source != "a"]
    return spec


def _cyclic() -> GraphSpec:
    spec = _linear(("a", "agent"), ("b", "memory"))
    spec.edges.append(EdgeSpec(id="back", source="b", target="a"))
    return spec


def _unreachable() -> GraphSpec:
    spec = _linear(("a", "agent"))
    spec.nodes.append(NodeSpec(id="island", type="memory", config=REPRESENTATIVE["memory"]))
    spec.edges.append(EdgeSpec(id="island-out", source="island", target="out"))
    return spec


def _undeclared_channel() -> GraphSpec:
    """A node writing a channel the caller never declared. `graph_channels` is what normally
    backfills it, so this builds the spec without that repair."""
    spec = _linear(("a", "memory"))
    spec.state = [c for c in BASE_STATE if c.key != "memory"]
    return spec


def _router_no_branches() -> GraphSpec:
    spec = _linear(("a", "router"))
    spec.nodes[1] = NodeSpec(
        id="a", type="router", config={**REPRESENTATIVE["router"], "branches": []}
    )
    return spec


def _router_branch_unwired() -> GraphSpec:
    """A router whose branches are declared but whose out-edge is labelled with only one."""
    spec = _linear(("a", "router"))
    spec.edges[-1] = EdgeSpec(id="e1", source="a", target="out", condition="summarize")
    return spec


def _react_branches_unwired() -> GraphSpec:
    """An agent wired to a Tool node with no 'tools'/'respond' labels — the ReAct loop the
    assistant used to invent before PR #41 gave it a worked example."""
    return _linear(("agent", "agent"), ("tools", "tool"))


def _tool_node_unbound() -> GraphSpec:
    """A Tool node fed by a Router: the exact topology behind the "I can't access Notion"
    report. Only Agent/Responder/Revisor bind tool schemas, so the model gets none."""
    spec = _linear(("router", "router"), ("tools", "tool"))
    spec.edges = [
        EdgeSpec(id="e0", source="in", target="router"),
        EdgeSpec(id="e1", source="router", target="tools", condition="summarize"),
        EdgeSpec(id="e2", source="router", target="out", condition="translate"),
        EdgeSpec(id="e3", source="tools", target="out"),
    ]
    return spec


def _routing_edge_unconditional() -> GraphSpec:
    """A Revisor wired straight to Output — the obvious thing to draw, and before this rule
    existed it validated clean and returned `output: None`, because the compiler drops an
    unlabelled out-edge from a branch-deciding node."""
    return _linear(("a", "responder"), ("b", "revisor"))


VIOLATIONS = {
    "bad_entry": _bad_entry,
    "no_entry": _no_entry,
    "duplicate_node_id": _duplicate_ids,
    "unknown_node_type": _unknown_type,
    "invalid_config": _invalid_config,
    "dangling_edge": _dangling_edge,
    "no_output": _no_output,
    "dead_end": _dead_end,
    "cyclic_graph": _cyclic,
    "unreachable": _unreachable,
    "undeclared_channel": _undeclared_channel,
    "router_no_branches": _router_no_branches,
    "router_branch_unwired": _router_branch_unwired,
    "react_branches_unwired": _react_branches_unwired,
    "tool_node_unbound": _tool_node_unbound,
    "routing_edge_unconditional": _routing_edge_unconditional,
}


@pytest.mark.parametrize("code", sorted(VIOLATIONS))
def test_each_validation_rule_fires_on_a_graph_that_breaks_it(code: str):
    issues = validate_graph(VIOLATIONS[code]())
    assert code in {i.code for i in issues}, (
        f"{code} did not fire — either the rule regressed or the fixture no longer breaks it"
    )


def test_every_rule_the_validator_can_emit_is_covered():
    """The meta-test. `validate_graph`'s vocabulary is read out of its own source, so adding a
    rule without a case above fails here instead of shipping untested — which is how
    `tool_node_unbound` got added reactively, after the bug it prevents had already escaped."""
    emitted = set(re.findall(r'code="([a-z_]+)"', inspect.getsource(validate_module)))
    assert emitted - set(VIOLATIONS) == set(), "validation rules with no test above"
    assert set(VIOLATIONS) - emitted == set(), "tests for rules the validator no longer emits"


# --- the specific regression -------------------------------------------------------------------


async def test_a_revisor_wired_to_output_is_refused_before_any_model_call():
    """Found by the pairwise sweep above. `compile.py` wires a branch-deciding node with
    `add_conditional_edges` (labelled edges only) and skips it in the plain-edge pass, so an
    unlabelled out-edge is discarded rather than merely unlabelled: the run ended at the Revisor
    and the user got an empty answer with nothing to explain it."""
    spec = _routing_edge_unconditional()
    issue = next(i for i in validate_graph(spec) if i.code == "routing_edge_unconditional")
    assert issue.severity == "error"
    assert issue.edge_id, "must name the edge to label, not just the node"
    assert "revise" in issue.message, "the message should say what to label it"
