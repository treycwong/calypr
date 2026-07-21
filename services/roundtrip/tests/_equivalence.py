"""The round-trip corpus + the equivalence primitives both test modules compare against.

Kept in one place so the Week-6 fixed-point suite and the Week-7 survival suite can't drift on
what "the same graph" means.
"""

from __future__ import annotations

from calypr_codegen.generate import _PYTYPE
from calypr_compiler import STARTERS
from calypr_compiler.golden import input_agent_output
from calypr_dsl import GraphSpec, StateChannel

# The golden builder plus every shipped starter template.
CORPUS: list[GraphSpec] = [input_agent_output(), *STARTERS]


def topology(graph: GraphSpec) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in graph.edges}


def channels(chs: list[StateChannel]) -> set[tuple[str, str, str]]:
    """Normalise each channel by the Python type the generator would emit, so the forward map's
    many-to-one lossiness (string/str → str) doesn't cause spurious inequality."""
    return {(c.key, str(c.reducer), _PYTYPE.get(c.type, "Any")) for c in chs}
