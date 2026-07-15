"""calypr-roundtrip — parse ownable LangGraph Python back into a GraphSpec.

The inverse of `calypr-codegen`. `generate_python` emits a *closed grammar* (a fixed
`build_graph()` shape + a `State` TypedDict), and this package walks that grammar back with
`ast` — never a general Python parser. Anything the walker doesn't recognise degrades to a
Custom Code node rather than failing the whole file (see `ParseResult.degraded_nodes`).

Recovers **topology + entry**, **state channels** (`State` TypedDict walker), and — via the
`# calypr:` metadata trailer that `generate_python` now emits — **identity + canvas layout**.
Per-node config recognisers (so nodes stop degrading to Custom Code) land in a later PR.
"""

from __future__ import annotations

from calypr_roundtrip.parse import ParseResult, parse_python

__all__ = ["ParseResult", "parse_python"]
