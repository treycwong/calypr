"""Week-7 edit-survival: what happens when a human edits the generated code before bringing it
back to the canvas?

The Week-6 suite proves the round-trip on *pristine* generated code. This one applies realistic
hand-edits (see `mutations.py`) across the whole corpus and measures what survives, so the
"you can edit your code" promise is a number rather than a hope.

Two tiers, deliberately different in strictness:

- **Robustness — must hold for every single (graph, edit) pair.** `parse_python` never raises;
  topology (node ids, edges, entry) and state channels come back exactly as the edit implies; and
  no node is ever **misclassified** — a node is either its true type or a degraded `code` node,
  never some *other* concrete type. This is the safety guarantee: a bad edit can cost you one
  node's structure, never silently corrupt the graph.
- **Clean absorption — measured, gated at ≥95%.** For edits that stay inside the generated idiom,
  the parser should recover them with no degradation at all and the change reflected in the
  config. Edits that leave the idiom (a rewritten docstring, a hand-written node) are expected to
  degrade *exactly* the node they touched.

`test_survival_rates` prints the per-edit-class table — the measured artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import mutations as mut
import pytest
from _equivalence import CORPUS, channels, topology
from calypr_codegen import generate_python
from calypr_dsl import GraphSpec
from calypr_roundtrip import parse_python

# The gate from MVP-EXECUTION-PLAN.md Week 7.
CLEAN_ABSORPTION_TARGET = 0.95


@dataclass
class Outcome:
    """One (graph, edit) pair's verdict."""

    graph_id: str
    mutation: str
    kind: str
    robust: bool = True
    clean: bool = True
    problems: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.graph_id}:{self.mutation}"


def _rename(value: str, renames: dict[str, str]) -> str:
    return renames.get(value, value)


def _evaluate(
    graph: GraphSpec, label: str, mutated: str, expect: mut.Expect, base: GraphSpec
) -> Outcome:
    """Judge one mutated module against the baseline parse + the edit's expectation."""
    kind = expect.kind or mut.KIND[mut.base_name(label)]
    out = Outcome(graph_id=graph.id, mutation=label, kind=kind)
    base_types = {n.id: n.type for n in base.nodes}

    try:
        result = parse_python(mutated)
    except Exception as exc:  # the parser must never raise on any edit
        out.robust = out.clean = False
        out.problems.append(f"parse raised: {exc!r}")
        return out
    spec = result.spec

    # --- topology: ids + edges must be exactly what the edit implies -------------------------
    want_ids = {_rename(i, expect.renames) for i in base_types} | expect.added_nodes
    got_ids = {n.id for n in spec.nodes}
    if got_ids != want_ids:
        out.robust = out.clean = False
        out.problems.append(f"node ids {sorted(got_ids)} != expected {sorted(want_ids)}")

    want_edges = {
        (_rename(s, expect.renames), _rename(t, expect.renames)) for s, t in topology(base)
    }
    want_edges = (want_edges | expect.added_edges) - expect.removed_edges
    got_edges = topology(spec)
    if got_edges != want_edges:
        out.robust = out.clean = False
        out.problems.append(f"edges {sorted(got_edges)} != expected {sorted(want_edges)}")

    if base.entry:
        want_entry = _rename(base.entry, expect.renames)
        if spec.entry != want_entry:
            out.robust = out.clean = False
            out.problems.append(f"entry {spec.entry!r} != expected {want_entry!r}")

    # --- state channels ------------------------------------------------------------------------
    if not expect.state_may_change and channels(spec.state) != channels(base.state):
        out.robust = out.clean = False
        out.problems.append("state channels changed unexpectedly")

    # --- no misclassification: a node is its true type, or degraded to `code` -----------------
    want_types = {_rename(i, expect.renames): t for i, t in base_types.items()}
    for node in spec.nodes:
        expected_type = want_types.get(node.id)
        if expected_type is None:  # a node the edit added
            continue
        if node.type not in (expected_type, "code"):
            out.robust = out.clean = False
            out.problems.append(
                f"{node.id!r} misclassified as {node.type!r} (true type {expected_type!r})"
            )

    # --- clean absorption: exactly the expected nodes degraded, and the edit landed -----------
    want_degraded = {_rename(i, expect.renames) for i in expect.degraded}
    if set(result.degraded_nodes) != want_degraded:
        out.clean = False
        out.problems.append(
            f"degraded {sorted(result.degraded_nodes)} != expected {sorted(want_degraded)}"
        )

    if expect.config_expect is not None:
        node_id, key, value = expect.config_expect
        node_id = _rename(node_id, expect.renames)
        node = next((n for n in spec.nodes if n.id == node_id), None)
        if node is None or node.config.get(key) != value:
            out.clean = False
            got = None if node is None else node.config.get(key)
            out.problems.append(f"{node_id!r}.{key} == {got!r}, expected {value!r}")

    return out


def _survey() -> list[Outcome]:
    """Every (graph, applicable edit) pair. Built once — generation shells out to ruff."""
    outcomes: list[Outcome] = []
    for graph in CORPUS:
        code = generate_python(graph)
        base = parse_python(code).spec
        for label, mutated, expect in mut.iter_mutations(code, graph):
            outcomes.append(_evaluate(graph, label, mutated, expect, base))
    return outcomes


SURVEY: list[Outcome] = _survey()


def test_corpus_is_meaningfully_covered() -> None:
    # Guard against the suite silently shrinking to nothing (e.g. every operator returning None).
    assert len(SURVEY) >= 200, f"only {len(SURVEY)} (graph, edit) pairs — corpus too thin"
    assert {o.kind for o in SURVEY} == {"absorb", "topology", "degrade"}


@pytest.mark.parametrize("outcome", SURVEY, ids=lambda o: o.id)
def test_robustness(outcome: Outcome) -> None:
    # Hard guarantee, every pair: no crash, topology/state intact, and never a misclassification.
    assert outcome.robust, "; ".join(outcome.problems)


@pytest.mark.parametrize(
    "outcome", [o for o in SURVEY if o.kind == "degrade"], ids=lambda o: o.id
)
def test_out_of_idiom_edits_degrade_exactly_the_touched_node(outcome: Outcome) -> None:
    # Leaving the idiom must cost exactly one node — never a cascade, never a wrong type.
    assert outcome.clean, "; ".join(outcome.problems)


def test_survival_rates() -> None:
    """The measured gate: robustness 100%, clean absorption ≥95% for in-idiom edits."""
    by_mutation: dict[str, list[Outcome]] = {}
    for o in SURVEY:
        by_mutation.setdefault(mut.base_name(o.mutation), []).append(o)

    rows = ["", f"{'edit':26} {'class':9} {'n':>4} {'robust':>8} {'clean':>8}"]
    for name, group in sorted(by_mutation.items(), key=lambda kv: (mut.KIND[kv[0]], kv[0])):
        kinds = {o.kind for o in group}
        label = next(iter(kinds)) if len(kinds) == 1 else "mixed"
        robust = sum(o.robust for o in group) / len(group)
        clean = sum(o.clean for o in group) / len(group)
        rows.append(f"{name:26} {label:9} {len(group):>4} {robust:>7.0%} {clean:>7.0%}")

    in_idiom = [o for o in SURVEY if o.kind in ("absorb", "topology")]
    robustness = sum(o.robust for o in SURVEY) / len(SURVEY)
    absorption = sum(o.clean for o in in_idiom) / len(in_idiom)
    rows += [
        "",
        f"robustness        {robustness:.1%} over {len(SURVEY)} (graph, edit) pairs",
        f"clean absorption  {absorption:.1%} over {len(in_idiom)} in-idiom pairs "
        f"(target ≥{CLEAN_ABSORPTION_TARGET:.0%})",
        "",
    ]
    table = "\n".join(rows)
    print(table)

    failures = [f"{o.id}: {'; '.join(o.problems)}" for o in SURVEY if not o.robust]
    assert robustness == 1.0, table + "\nrobustness violations:\n" + "\n".join(failures)
    assert absorption >= CLEAN_ABSORPTION_TARGET, table + "\nnot cleanly absorbed:\n" + "\n".join(
        f"{o.id}: {'; '.join(o.problems)}" for o in in_idiom if not o.clean
    )
