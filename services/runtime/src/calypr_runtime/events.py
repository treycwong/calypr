"""Events surfaced by a streaming run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class RunEvent:
    # `asset`: a media node durably stored a generated file. Carried in `state`, like `usage`.
    type: Literal["token", "usage", "final", "node", "asset"]
    text: str = ""
    output: str = ""
    state: dict[str, Any] | None = None
    # Populated only for `node` events: which node entered/left, and which phase.
    node_id: str = ""
    phase: str = ""
